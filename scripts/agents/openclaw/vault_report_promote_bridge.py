"""Bridge for promoting a draft-staged inbox note to report stage.

Reads an existing note from Agent/Inbox_Agent/ that has already been promoted
to draft (capture_status == "promoted_to_draft"), writes REPORT_INPUT.md in
the same directory for the report pipeline using the manual promotion helper's
build_document(), and marks the source note as promoted_to_report.

Design note: this action completes the inbox → draft → report lifecycle.
The source note remains in place as an audit trail; only its capture_status
field is mutated.  STAGED_INPUT.md is NOT consumed here — the draft pipeline
is expected to have handled it before report.promote is invoked.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — same pattern as vault_draft_promote_bridge.py
# ---------------------------------------------------------------------------
_HELPERS_DIR = Path(__file__).resolve().parent.parent.parent / "helpers"
if str(_HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPERS_DIR))

from openclaw_manual_promotion_helper import (  # noqa: E402
    DOMAIN_SPECS,
    HelperError,
    assert_no_symlinks,
    build_document,
    ensure_existing_directory,
    ensure_existing_file,
    parse_frontmatter_scalar,
    split_frontmatter,
)

from openclaw_vault_inbox_writer import (  # noqa: E402
    ALLOWED_OUTPUT_DIR,
    is_relative_to,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INBOX_NOTE_PATTERN = re.compile(r"^\d{8}T\d{6}Z_inbox_[\w.\-]+\.md$")
REPORTABLE_STATUS = "promoted_to_draft"
REPORTED_STATUS = "promoted_to_report"
REPORT_SPEC = DOMAIN_SPECS["report"]
MAX_LIST_RESULTS = 10


class VaultReportPromoteBridgeError(RuntimeError):
    """Raised when report promotion fails for a reason safe to surface."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_inbox_dir(vault_root: str) -> tuple[Path, Path]:
    """Validate vault_root and return (resolved_vault, resolved_inbox)."""
    vault_path = Path(vault_root)
    if not vault_path.is_absolute():
        raise VaultReportPromoteBridgeError("invalid_config", "vault_root must be an absolute path")
    try:
        assert_no_symlinks(vault_path, "vault_root")
        resolved_vault = vault_path.resolve(strict=True)
    except (HelperError, OSError) as exc:
        raise VaultReportPromoteBridgeError("invalid_config", f"vault_root not accessible: {exc}") from exc

    inbox_candidate = resolved_vault / ALLOWED_OUTPUT_DIR
    try:
        assert_no_symlinks(inbox_candidate, "inbox directory")
        ensure_existing_directory(inbox_candidate, "inbox directory")
    except HelperError as exc:
        raise VaultReportPromoteBridgeError("destination_missing", str(exc)) from exc

    resolved_inbox = inbox_candidate.resolve(strict=True)
    if not is_relative_to(resolved_inbox, resolved_vault):
        raise VaultReportPromoteBridgeError("invalid_config", "inbox directory is outside vault_root")

    return resolved_vault, resolved_inbox


def _parse_inbox_frontmatter(content: str) -> dict[str, str]:
    """Extract key-value pairs from an inbox note's YAML-like frontmatter."""
    frontmatter_lines, _ = split_frontmatter(content)
    fields: dict[str, str] = {}
    for line in frontmatter_lines:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        fields[key] = parse_frontmatter_scalar(raw_value, key)
    return fields


def _extract_title(body_after_fm: str, note_name: str) -> str:
    """Find the first top-level heading after frontmatter."""
    for line in body_after_fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return f"Report from {note_name}"


def _extract_capture_body(body_after_fm: str, note_name: str) -> str:
    """Extract text between ## Captura and next ## heading."""
    lines: list[str] = []
    in_capture = False
    for line in body_after_fm.splitlines():
        stripped = line.strip()
        if stripped == "## Captura":
            in_capture = True
            continue
        if in_capture and stripped.startswith("## "):
            break
        if in_capture:
            lines.append(line)
    body = "\n".join(lines).strip()
    return body if body else f"Promoted from draft note: {note_name}"


def _write_create_only(path: Path, content: str, label: str) -> None:
    """Write content to path using O_CREAT|O_EXCL (create-only)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = None
    try:
        fd = os.open(path, flags | nofollow, 0o660)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(content)
    except FileExistsError as exc:
        raise VaultReportPromoteBridgeError(
            "report_conflict", f"{label} already exists: {path}"
        ) from exc
    except OSError as exc:
        raise VaultReportPromoteBridgeError(
            "write_failed", f"failed to write {label}: {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_reportable_notes(*, vault_root: str, max_results: int = MAX_LIST_RESULTS) -> list[dict[str, Any]]:
    """List inbox notes with capture_status == promoted_to_draft (ready to report).

    Returns a list of dicts with: note_name, run_id, created_at_utc, status.
    Sorted newest-first.  Safe to call as a read-only operation.
    """
    vault_path = Path(vault_root)
    inbox_dir = vault_path / ALLOWED_OUTPUT_DIR
    if not inbox_dir.is_dir():
        return []

    candidates = sorted(
        [f for f in inbox_dir.iterdir() if f.is_file() and INBOX_NOTE_PATTERN.match(f.name)],
        key=lambda f: f.name,
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for note_path in candidates[: max_results * 3]:
        try:
            content = note_path.read_text(encoding="utf-8")
            fields = _parse_inbox_frontmatter(content)
            if fields.get("capture_status") == REPORTABLE_STATUS:
                results.append({
                    "note_name": note_path.name,
                    "run_id": fields.get("run_id", "?"),
                    "created_at_utc": fields.get("created_at_utc", "?"),
                    "status": REPORTABLE_STATUS,
                })
                if len(results) >= max_results:
                    break
        except Exception:
            continue

    return results


def invoke_report_promote(*, vault_root: str, note_name: str) -> dict[str, Any]:
    """Promote a draft-staged inbox note to report stage.

    1. Validates the note exists and has capture_status == promoted_to_draft
    2. Writes REPORT_INPUT.md in Agent/Inbox_Agent/ for the report pipeline
    3. Marks source note capture_status → promoted_to_report

    Returns metadata dict.  Raises VaultReportPromoteBridgeError on failure.
    """
    _, resolved_inbox = _resolve_inbox_dir(vault_root)

    # --- validate note_name ---
    if not INBOX_NOTE_PATTERN.match(note_name):
        raise VaultReportPromoteBridgeError(
            "invalid_params", "note_name does not match inbox naming pattern"
        )

    note_path = resolved_inbox / note_name
    if note_path.parent != resolved_inbox:
        raise VaultReportPromoteBridgeError(
            "invalid_params", "note_name resolves outside inbox directory"
        )

    try:
        ensure_existing_file(note_path, "inbox note")
    except HelperError as exc:
        raise VaultReportPromoteBridgeError("not_found", str(exc)) from exc

    # --- read & parse ---
    content = note_path.read_text(encoding="utf-8")

    try:
        fields = _parse_inbox_frontmatter(content)
    except HelperError as exc:
        raise VaultReportPromoteBridgeError(
            "invalid_note", f"cannot parse frontmatter: {exc}"
        ) from exc

    current_status = fields.get("capture_status", "")
    if current_status != REPORTABLE_STATUS:
        raise VaultReportPromoteBridgeError(
            "not_reportable",
            f"note status is '{current_status}', expected '{REPORTABLE_STATUS}'",
        )

    run_id = fields.get("run_id", "")
    if not run_id:
        raise VaultReportPromoteBridgeError("invalid_note", "note is missing run_id")

    try:
        _, body_after_fm = split_frontmatter(content)
    except HelperError as exc:
        raise VaultReportPromoteBridgeError("invalid_note", str(exc)) from exc

    title = _extract_title(body_after_fm, note_name)
    body = _extract_capture_body(body_after_fm, note_name)
    source_refs = [f"inbox:{note_name}"]

    # --- check no pending report file ---
    report_path = resolved_inbox / REPORT_SPEC.output_name
    if report_path.exists():
        raise VaultReportPromoteBridgeError(
            "report_conflict",
            "REPORT_INPUT.md already exists — a previous report promotion may be pending processing",
        )

    # --- write REPORT_INPUT.md (create-only) ---
    report_content = build_document(
        REPORT_SPEC,
        run_id=run_id,
        title=title,
        body=body,
        source_refs=source_refs,
        proposed_target_path="",
    )
    _write_create_only(report_path, report_content, "REPORT_INPUT.md")

    # --- mark source note as promoted to report ---
    marker_old = f'capture_status: "{REPORTABLE_STATUS}"'
    marker_new = f'capture_status: "{REPORTED_STATUS}"'
    new_content = content.replace(marker_old, marker_new, 1)

    if new_content == content:
        # Cannot mark — clean up report file
        try:
            report_path.unlink()
        except OSError:
            pass
        raise VaultReportPromoteBridgeError(
            "mark_failed",
            "could not locate capture_status field in source note for update",
        )

    try:
        note_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        try:
            report_path.unlink()
        except OSError:
            pass
        raise VaultReportPromoteBridgeError(
            "mark_failed", f"failed to update source note: {exc}"
        ) from exc

    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "note_name": note_name,
        "run_id": run_id,
        "original_status": REPORTABLE_STATUS,
        "new_status": REPORTED_STATUS,
        "report_path": str(report_path),
        "source_path": str(note_path),
        "promoted_at_utc": now_utc,
        "title": title,
        "body_bytes": len(body.encode("utf-8")),
    }
