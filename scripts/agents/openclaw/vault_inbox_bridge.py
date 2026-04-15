"""Bridge between restricted operator broker and openclaw_vault_inbox_writer.

Provides a single entry point invoke_inbox_write() that reuses the writer's
validated sanitization and write primitives directly, without requiring an
intermediate input file on disk.

This module adjusts sys.path to locate openclaw_vault_inbox_writer.py, which
lives in scripts/helpers/ relative to the repo root.  The path insertion is
intentional and documented: this is an internal repo dependency, not an
external package.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Resolve the helpers directory relative to this file so the bridge works from
# any working directory without requiring PYTHONPATH to be set externally.
_HELPERS_DIR = Path(__file__).resolve().parent.parent.parent / "helpers"
if str(_HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPERS_DIR))

from openclaw_vault_inbox_writer import (  # noqa: E402
    ALLOWED_OUTPUT_DIR,
    MAX_BODY_BYTES,
    MAX_TITLE_BYTES,
    InboxWriteRequest,
    WriterError,
    assert_no_symlinks,
    build_markdown,
    build_note_name,
    ensure_existing_directory,
    is_relative_to,
    sanitize_body_text,
    sanitize_component,
    sanitize_single_line_text,
    sanitize_source_refs,
    sha256_hex,
    timestamp_for_filename,
    timestamp_for_frontmatter,
    utc_now,
    write_create_only,
)


class VaultInboxBridgeError(RuntimeError):
    """Raised when the vault inbox write fails for a reason safe to surface."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def invoke_inbox_write(
    *,
    vault_root: str,
    run_id: str,
    capture_title: str,
    capture_body: str,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Write a single create-only inbox note into vault_root/Agent/Inbox_Agent.

    Parameters are validated using the writer's sanitization functions so the
    same invariants are enforced whether the call comes from the CLI writer or
    from the broker action.

    Returns a dict with: note_path, note_name, run_id, bytes_written, sha256,
    timestamp_utc.

    Raises VaultInboxBridgeError on any validation or I/O failure.
    """
    now = utc_now()
    refs = source_refs or []

    try:
        safe_run_id = sanitize_component(run_id, "run_id")
        safe_title = sanitize_single_line_text(capture_title, "capture_title", max_bytes=MAX_TITLE_BYTES)
        safe_body = sanitize_body_text(capture_body, "capture_body", max_bytes=MAX_BODY_BYTES)
        safe_refs = sanitize_source_refs(refs)
    except WriterError as exc:
        raise VaultInboxBridgeError("invalid_params", str(exc)) from exc

    vault_path = Path(vault_root)
    if not vault_path.is_absolute():
        raise VaultInboxBridgeError("invalid_config", "vault_root must be an absolute path")
    try:
        assert_no_symlinks(vault_path, "vault_root")
        resolved_vault = vault_path.resolve(strict=True)
    except (WriterError, OSError) as exc:
        raise VaultInboxBridgeError("invalid_config", f"vault_root not accessible: {exc}") from exc

    try:
        ensure_existing_directory(resolved_vault, "vault_root")
    except WriterError as exc:
        raise VaultInboxBridgeError("invalid_config", str(exc)) from exc

    destination_candidate = resolved_vault / ALLOWED_OUTPUT_DIR
    try:
        assert_no_symlinks(destination_candidate, "destination directory")
        ensure_existing_directory(destination_candidate, "destination directory")
    except WriterError as exc:
        raise VaultInboxBridgeError("destination_missing", str(exc)) from exc

    try:
        destination_dir = destination_candidate.resolve(strict=True)
    except OSError as exc:
        raise VaultInboxBridgeError("destination_missing", f"cannot resolve destination: {exc}") from exc

    if not is_relative_to(destination_dir, resolved_vault):
        raise VaultInboxBridgeError("invalid_config", "destination directory is outside vault_root")

    request = InboxWriteRequest(
        operation="inbox.write",
        schema_version=1,
        run_id=safe_run_id,
        capture_title=safe_title,
        capture_body=safe_body,
        source_refs=safe_refs,
    )

    note_name = build_note_name(timestamp_for_filename(now), request.run_id)
    note_path = destination_dir / note_name
    if note_path.parent != destination_dir:
        raise VaultInboxBridgeError("invalid_params", "computed note path escaped destination directory")

    markdown = build_markdown(now=now, request=request, input_rel_hint="telegram/inbox_write")

    try:
        write_create_only(note_path, markdown, "inbox note")
    except WriterError as exc:
        raise VaultInboxBridgeError("write_failed", str(exc)) from exc

    output_bytes = markdown.encode("utf-8")
    return {
        "note_path": str(note_path),
        "note_name": note_name,
        "run_id": safe_run_id,
        "bytes_written": len(output_bytes),
        "sha256": sha256_hex(output_bytes),
        "timestamp_utc": timestamp_for_frontmatter(now),
    }


