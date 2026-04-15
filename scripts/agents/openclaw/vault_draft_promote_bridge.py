"""Bridge for promoting an inbox note to draft stage.

Reads an existing note from Agent/Inbox_Agent/, validates it is promotable
(capture_status == "pending_triage"), writes STAGED_INPUT.md for the draft
pipeline using the manual promotion helper's build_document(), and marks the
source note as promoted_to_draft.

Design note: updating capture_status in the source note is a deliberate
single-field status transition on a note the agent owns.  This differs from
the create-only semantics of inbox.write and is documented as intentional.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — same pattern as vault_inbox_bridge.py
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
PROMOTABLE_STATUS = "pending_triage"
PROMOTED_STATUS = "promoted_to_draft"
DRAFT_SPEC = DOMAIN_SPECS["draft"]
MAX_LIST_RESULTS = 10


class VaultDraftPromoteBridgeError(RuntimeError):
    """Raised when draft promotion fails for a reason safe to surface."""

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
        raise VaultDraftPromoteBridgeError("invalid_config", "vault_root must be an absolute path")
    try:
        assert_no_symlinks(vault_path, "vault_root")
        resolved_vault = vault_path.resolve(strict=True)
    except (HelperError, OSError) as exc:
        raise VaultDraftPromoteBridgeError("invalid_config", f"vault_root not accessible: {exc}") from exc

    inbox_candidate = resolved_vault / ALLOWED_OUTPUT_DIR
    try:
        assert_no_symlinks(inbox_candidate, "inbox directory")
        ensure_existing_directory(inbox_candidate, "inbox directory")
    except HelperError as exc:
        raise VaultDraftPromoteBridgeError("destination_missing", str(exc)) from exc

    resolved_inbox = inbox_candidate.resolve(strict=True)
    if not is_relative_to(resolved_inbox, resolved_vault):
        raise VaultDraftPromoteBridgeError("invalid_config", "inbox directory is outside vault_root")

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
        # source_refs is a JSON array — keep raw for separate parsing
        if key == "source_refs":
            fields[key] = raw_value.strip()
        else:
            fields[key] = parse_frontmatter_scalar(raw_value, key)
    return fields


def _extract_title(body_after_fm: str, note_name: str) -> str:
    """Find the first top-level heading after frontmatter."""
    for line in body_after_fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return f"Draft from {note_name}"


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
    return body if body else f"Promoted from inbox note: {note_name}"


def _parse_source_refs(raw: str) -> list[str]:
    """Parse source_refs from raw frontmatter value (JSON array string)."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(r) for r in parsed if isinstance(r, str) and r]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


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
        raise VaultDraftPromoteBridgeError(
            "staging_conflict", f"{label} already exists: {path}"
        ) from exc
    except OSError as exc:
        raise VaultDraftPromoteBridgeError(
            "write_failed", f"failed to write {label}: {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_promotable_notes(*, vault_root: str, max_results: int = MAX_LIST_RESULTS) -> list[dict[str, Any]]:
    """List inbox notes with capture_status == pending_triage.

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
            if fields.get("capture_status") == PROMOTABLE_STATUS:
                results.append({
                    "note_name": note_path.name,
                    "run_id": fields.get("run_id", "?"),
                    "created_at_utc": fields.get("created_at_utc", "?"),
                    "status": PROMOTABLE_STATUS,
                })
                if len(results) >= max_results:
                    break
        except Exception:
            continue

    return results


def invoke_draft_promote(*, vault_root: str, note_name: str) -> dict[str, Any]:
    """Promote an inbox note to draft stage.

    1. Validates the note exists and has capture_status == pending_triage
    2. Writes STAGED_INPUT.md in Agent/Inbox_Agent/ for the draft pipeline
    3. Marks source note capture_status → promoted_to_draft

    Returns metadata dict.  Raises VaultDraftPromoteBridgeError on failure.
    """
    _, resolved_inbox = _resolve_inbox_dir(vault_root)

    # --- validate note_name ---
    if not INBOX_NOTE_PATTERN.match(note_name):
        raise VaultDraftPromoteBridgeError(
            "invalid_params", "note_name does not match inbox naming pattern"
        )

    note_path = resolved_inbox / note_name
    if note_path.parent != resolved_inbox:
        raise VaultDraftPromoteBridgeError(
            "invalid_params", "note_name resolves outside inbox directory"
        )

    try:
        ensure_existing_file(note_path, "inbox note")
    except HelperError as exc:
        raise VaultDraftPromoteBridgeError("not_found", str(exc)) from exc

    # --- read & parse ---
    content = note_path.read_text(encoding="utf-8")

    try:
        fields = _parse_inbox_frontmatter(content)
    except HelperError as exc:
        raise VaultDraftPromoteBridgeError(
            "invalid_note", f"cannot parse frontmatter: {exc}"
        ) from exc

    current_status = fields.get("capture_status", "")
    if current_status != PROMOTABLE_STATUS:
        raise VaultDraftPromoteBridgeError(
            "not_promotable",
            f"note status is '{current_status}', expected '{PROMOTABLE_STATUS}'",
        )

    run_id = fields.get("run_id", "")
    if not run_id:
        raise VaultDraftPromoteBridgeError("invalid_note", "note is missing run_id")

    try:
        _, body_after_fm = split_frontmatter(content)
    except HelperError as exc:
        raise VaultDraftPromoteBridgeError("invalid_note", str(exc)) from exc

    title = _extract_title(body_after_fm, note_name)
    body = _extract_capture_body(body_after_fm, note_name)
    source_refs = _parse_source_refs(fields.get("source_refs", ""))
    source_refs.append(f"inbox:{note_name}")

    # --- check no pending staging file ---
    staged_path = resolved_inbox / DRAFT_SPEC.output_name
    if staged_path.exists():
        raise VaultDraftPromoteBridgeError(
            "staging_conflict",
            "STAGED_INPUT.md already exists — a previous promotion may be pending processing",
        )

    # --- write STAGED_INPUT.md (create-only) ---
    staged_content = build_document(
        DRAFT_SPEC,
        run_id=run_id,
        title=title,
        body=body,
        source_refs=source_refs,
        proposed_target_path="",
    )
    _write_create_only(staged_path, staged_content, "STAGED_INPUT.md")

    # --- mark source note as promoted ---
    marker_old = f'capture_status: "{PROMOTABLE_STATUS}"'
    marker_new = f'capture_status: "{PROMOTED_STATUS}"'
    new_content = content.replace(marker_old, marker_new, 1)

    if new_content == content:
        # Cannot mark — clean up staged file
        try:
            staged_path.unlink()
        except OSError:
            pass
        raise VaultDraftPromoteBridgeError(
            "mark_failed",
            "could not locate capture_status field in source note for update",
        )

    try:
        note_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        try:
            staged_path.unlink()
        except OSError:
            pass
        raise VaultDraftPromoteBridgeError(
            "mark_failed", f"failed to update source note: {exc}"
        ) from exc

    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "note_name": note_name,
        "run_id": run_id,
        "original_status": PROMOTABLE_STATUS,
        "new_status": PROMOTED_STATUS,
        "staged_path": str(staged_path),
        "source_path": str(note_path),
        "promoted_at_utc": now_utc,
        "title": title,
        "body_bytes": len(body.encode("utf-8")),
    }
