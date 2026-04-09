#!/usr/bin/env python3
"""Minimal host-side writer for a single create-only inbox.write operation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MANAGED_BY = "openclaw"
AGENT_ZONE = "Inbox_Agent"
ALLOWED_OUTPUT_DIR = Path("Agent/Inbox_Agent")
ALLOWED_OPERATION = "inbox.write"
ALLOWED_SCHEMA_VERSION = 1
CANONICAL_INPUT_DIR_NAME = "openclaw-vault-inbox-writer"
CANONICAL_INPUT_NAME = "INBOX_INPUT.md"
REQUIRED_FRONTMATTER_KEYS = {
    "capture_title",
    "operation",
    "run_id",
    "schema_version",
}
OPTIONAL_FRONTMATTER_KEYS = {
    "source_refs",
}
ALLOWED_FRONTMATTER_KEYS = REQUIRED_FRONTMATTER_KEYS | OPTIONAL_FRONTMATTER_KEYS
MAX_COMPONENT_LEN = 64
MAX_FILENAME_LEN = 160
MAX_INPUT_BYTES = 16 * 1024
MAX_BODY_BYTES = 16 * 1024
MAX_TITLE_BYTES = 160
AUDIT_LOG_NAME = "inbox-writer-audit.jsonl"


@dataclass(frozen=True)
class InboxWriteRequest:
    operation: str
    schema_version: int
    run_id: str
    capture_title: str
    capture_body: str
    source_refs: list[str]


class WriterError(RuntimeError):
    """Raised when the writer must stop for safety reasons."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a single create-only inbox note inside Agent/Inbox_Agent."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    write_parser = subparsers.add_parser(ALLOWED_OPERATION)
    write_parser.add_argument("--vault-root", required=True)
    write_parser.add_argument("--audit-root", required=True)
    write_parser.add_argument("--input-request-file", required=True)
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_for_filename(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def timestamp_for_frontmatter(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_component(value: str, label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise WriterError(f"{label} is empty after sanitization")
    if len(cleaned) > MAX_COMPONENT_LEN:
        raise WriterError(f"{label} exceeds {MAX_COMPONENT_LEN} characters")
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise WriterError(f"{label} contains invalid path content")
    return cleaned


def sanitize_source_refs(values: Iterable[str]) -> list[str]:
    sanitized: list[str] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise WriterError("source_refs contains an empty value")
        if "\x00" in value or "\n" in value or "\r" in value:
            raise WriterError("source_refs contains invalid control characters")
        sanitized.append(value)
    return sanitized


def sanitize_body_text(value: str, label: str, *, max_bytes: int) -> str:
    if "\x00" in value:
        raise WriterError(f"{label} contains invalid control characters")
    cleaned = value.strip()
    if not cleaned:
        raise WriterError(f"{label} cannot be empty")
    if len(cleaned.encode("utf-8")) > max_bytes:
        raise WriterError(f"{label} exceeds {max_bytes} bytes")
    return cleaned


def sanitize_single_line_text(value: str, label: str, *, max_bytes: int) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise WriterError(f"{label} contains invalid control characters")
    cleaned = value.strip()
    if not cleaned:
        raise WriterError(f"{label} cannot be empty")
    if len(cleaned.encode("utf-8")) > max_bytes:
        raise WriterError(f"{label} exceeds {max_bytes} bytes")
    return cleaned


def ensure_existing_directory(path: Path, label: str) -> None:
    try:
        path_lstat = path.lstat()
    except FileNotFoundError as exc:
        raise WriterError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(path_lstat.st_mode):
        raise WriterError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISDIR(path_lstat.st_mode):
        raise WriterError(f"{label} must be a directory: {path}")


def ensure_existing_file(path: Path, label: str) -> None:
    try:
        path_lstat = path.lstat()
    except FileNotFoundError as exc:
        raise WriterError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(path_lstat.st_mode):
        raise WriterError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(path_lstat.st_mode):
        raise WriterError(f"{label} must be a regular file: {path}")


def assert_no_symlinks(path: Path, label: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        try:
            path_lstat = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(path_lstat.st_mode):
            raise WriterError(f"{label} contains a symlink component: {current}")


def resolve_existing_directory(path_str: str, label: str) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        raise WriterError(f"{label} must be an absolute path")
    assert_no_symlinks(candidate, label)
    resolved = candidate.resolve(strict=True)
    ensure_existing_directory(resolved, label)
    return resolved


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def ensure_directory(path: Path, label: str) -> None:
    if path.exists():
        ensure_existing_directory(path, label)
        return
    parent = path.parent
    ensure_existing_directory(parent, f"{label} parent")
    assert_no_symlinks(parent, f"{label} parent")
    try:
        path.mkdir(mode=0o750)
    except FileExistsError as exc:
        raise WriterError(f"{label} already exists but is not a directory: {path}") from exc
    ensure_existing_directory(path, label)


def split_frontmatter(document_text: str) -> tuple[list[str], str]:
    lines = document_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise WriterError("input-request-file must start with frontmatter delimiter ---")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise WriterError("input-request-file is missing closing frontmatter delimiter ---")
    return lines[1:closing_index], "\n".join(lines[closing_index + 1 :])


def parse_frontmatter_scalar(raw_value: str, label: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WriterError(f"{label} is not valid JSON string syntax") from exc
        if not isinstance(parsed, str):
            raise WriterError(f"{label} must decode to a string")
        return parsed
    return value


def parse_frontmatter_int(raw_value: str, label: str) -> int:
    value = raw_value.strip()
    if not re.fullmatch(r"[0-9]+", value):
        raise WriterError(f"{label} must be an integer")
    return int(value)


def parse_frontmatter_string_list(raw_value: str, label: str) -> list[str]:
    value = raw_value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise WriterError(f"{label} must use inline JSON array syntax") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise WriterError(f"{label} must be a list of strings")
    return sanitize_source_refs(parsed)


def read_input_bytes(path: Path) -> bytes:
    ensure_existing_file(path, "input-request-file")
    size_bytes = path.stat().st_size
    if size_bytes > MAX_INPUT_BYTES:
        raise WriterError(f"input-request-file exceeds {MAX_INPUT_BYTES} bytes")
    content = path.read_bytes()
    if not content.strip():
        raise WriterError("input-request-file is empty")
    return content


def decode_utf8_text(raw_bytes: bytes, label: str) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WriterError(f"{label} is not valid UTF-8") from exc


def parse_request(document_text: str) -> InboxWriteRequest:
    frontmatter_lines, body_text = split_frontmatter(document_text)
    raw_fields: dict[str, str] = {}

    for line_number, line in enumerate(frontmatter_lines, start=2):
        if not line.strip():
            raise WriterError(f"frontmatter line {line_number} must not be empty")
        if ":" not in line:
            raise WriterError(f"frontmatter line {line_number} is missing ':'")
        key, raw_value = line.split(":", 1)
        normalized_key = key.strip()
        if normalized_key not in ALLOWED_FRONTMATTER_KEYS:
            raise WriterError(f"frontmatter key is not allowed: {normalized_key}")
        if normalized_key in raw_fields:
            raise WriterError(f"frontmatter key is duplicated: {normalized_key}")
        raw_fields[normalized_key] = raw_value

    missing_keys = sorted(REQUIRED_FRONTMATTER_KEYS - raw_fields.keys())
    if missing_keys:
        raise WriterError(
            "input-request-file is missing required frontmatter keys: "
            + ", ".join(missing_keys)
        )

    operation = parse_frontmatter_scalar(raw_fields["operation"], "operation")
    if operation != ALLOWED_OPERATION:
        raise WriterError(f"operation must be {ALLOWED_OPERATION}")

    schema_version = parse_frontmatter_int(raw_fields["schema_version"], "schema_version")
    if schema_version != ALLOWED_SCHEMA_VERSION:
        raise WriterError(f"schema_version must be {ALLOWED_SCHEMA_VERSION}")

    run_id = sanitize_component(
        parse_frontmatter_scalar(raw_fields["run_id"], "run_id"),
        "run_id",
    )
    capture_title = sanitize_single_line_text(
        parse_frontmatter_scalar(raw_fields["capture_title"], "capture_title"),
        "capture_title",
        max_bytes=MAX_TITLE_BYTES,
    )
    source_refs = parse_frontmatter_string_list(raw_fields.get("source_refs", ""), "source_refs")
    capture_body = sanitize_body_text(body_text, "capture_body", max_bytes=MAX_BODY_BYTES)

    return InboxWriteRequest(
        operation=operation,
        schema_version=schema_version,
        run_id=run_id,
        capture_title=capture_title,
        capture_body=capture_body,
        source_refs=source_refs,
    )


def build_note_name(timestamp_utc: str, run_id: str) -> str:
    filename = f"{timestamp_utc}_inbox_{run_id}.md"
    if len(filename) > MAX_FILENAME_LEN:
        raise WriterError(f"filename exceeds {MAX_FILENAME_LEN} characters")
    if not filename.endswith(".md"):
        raise WriterError("filename must end with .md")
    return filename


def dump_yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def build_markdown(
    now: datetime,
    request: InboxWriteRequest,
    input_rel_hint: str,
) -> str:
    timestamp_utc = timestamp_for_frontmatter(now)
    frontmatter_lines = [
        "---",
        f"managed_by: {MANAGED_BY}",
        f"agent_zone: {AGENT_ZONE}",
        f"run_id: {dump_yaml_scalar(request.run_id)}",
        f"created_at_utc: {dump_yaml_scalar(timestamp_utc)}",
        f"updated_at_utc: {dump_yaml_scalar(timestamp_utc)}",
        f"source_refs: {json.dumps(request.source_refs, ensure_ascii=True)}",
        'capture_status: "pending_triage"',
        "---",
        "",
        f"# {request.capture_title}",
        "",
        "## Contexto",
        "",
        "Captura rapida create-only para triage posterior dentro de Agent/Inbox_Agent.",
        "",
        "## Entrada",
        "",
        f"- input_request_file: `{input_rel_hint}`",
        "",
        "## Captura",
        "",
        request.capture_body,
        "",
        "## Trazabilidad",
        "",
        f"- operation: `{request.operation}`",
        f"- run_id: `{request.run_id}`",
        f"- created_at_utc: `{timestamp_utc}`",
        f"- source_refs: `{json.dumps(request.source_refs, ensure_ascii=True)}`",
        "",
    ]
    return "\n".join(frontmatter_lines)


def write_create_only(path: Path, content: str, label: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = None
    try:
        fd = os.open(path, flags | nofollow, 0o660)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(content)
    except FileExistsError as exc:
        raise WriterError(f"{label} already exists: {path}") from exc
    except OSError as exc:
        raise WriterError(f"failed to write {label}: {path}: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def prepare_audit_root(audit_root: Path, vault_root: Path) -> Path:
    if not audit_root.is_absolute():
        raise WriterError("audit-root must be an absolute path")
    assert_no_symlinks(audit_root, "audit-root")
    normalized = audit_root.resolve()
    if is_relative_to(normalized, vault_root):
        raise WriterError("audit-root must be outside the vault")
    ensure_directory(normalized, "audit-root")
    return normalized


def append_audit_record(audit_root: Path, record: dict[str, object]) -> Path:
    audit_log_path = audit_root / AUDIT_LOG_NAME
    if audit_log_path.exists():
        audit_lstat = audit_log_path.lstat()
        if stat.S_ISLNK(audit_lstat.st_mode):
            raise WriterError(f"audit log must not be a symlink: {audit_log_path}")
        if not stat.S_ISREG(audit_lstat.st_mode):
            raise WriterError(f"audit log must be a regular file: {audit_log_path}")

    payload = json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = None
    try:
        fd = os.open(audit_log_path, flags | nofollow, 0o640)
        with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(payload)
    except OSError as exc:
        raise WriterError(f"failed to write audit log: {audit_log_path}: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)

    return audit_log_path


def perform_inbox_write(args: argparse.Namespace) -> int:
    now = utc_now()
    vault_root = resolve_existing_directory(args.vault_root, "vault-root")
    destination_candidate = vault_root / ALLOWED_OUTPUT_DIR
    assert_no_symlinks(destination_candidate, "destination directory")
    ensure_existing_directory(destination_candidate, "destination directory")
    destination_dir = destination_candidate.resolve(strict=True)
    if not is_relative_to(destination_dir, vault_root):
        raise WriterError("destination directory is outside the vault")

    input_candidate = Path(args.input_request_file)
    if not input_candidate.is_absolute():
        raise WriterError("input-request-file must be an absolute path")
    assert_no_symlinks(input_candidate, "input-request-file")
    input_path = input_candidate.resolve(strict=True)
    ensure_existing_file(input_path, "input-request-file")
    if input_path.suffix.lower() != ".md":
        raise WriterError("input-request-file must end with .md")
    if input_path.name != CANONICAL_INPUT_NAME:
        raise WriterError(
            f"input-request-file must use the canonical name {CANONICAL_INPUT_NAME}"
        )
    if input_path.parent.name != CANONICAL_INPUT_DIR_NAME:
        raise WriterError(
            "input-request-file must live directly in the canonical input directory"
        )
    if is_relative_to(input_path, vault_root):
        raise WriterError("input-request-file must live outside the vault")

    audit_root = prepare_audit_root(Path(args.audit_root), vault_root)

    input_bytes = read_input_bytes(input_path)
    input_text = decode_utf8_text(input_bytes, "input-request-file")
    request = parse_request(input_text)

    note_name = build_note_name(timestamp_for_filename(now), request.run_id)
    note_path = destination_dir / note_name
    if note_path.parent != destination_dir:
        raise WriterError("computed note path escaped destination directory")
    if note_path.exists():
        raise WriterError(f"destination already exists: {note_path}")

    input_rel_hint = f"{input_path.parent.name}/{input_path.name}"
    markdown = build_markdown(
        now=now,
        request=request,
        input_rel_hint=input_rel_hint,
    )
    write_create_only(note_path, markdown, "inbox note")

    output_bytes = markdown.encode("utf-8")
    audit_record = {
        "event_at_utc": timestamp_for_frontmatter(now),
        "managed_by": MANAGED_BY,
        "agent_zone": AGENT_ZONE,
        "operation": request.operation,
        "schema_version": request.schema_version,
        "run_id": request.run_id,
        "input_path": str(input_path),
        "input_size_bytes": len(input_bytes),
        "input_sha256": sha256_hex(input_bytes),
        "note_path": str(note_path),
        "output_size_bytes": len(output_bytes),
        "output_sha256": sha256_hex(output_bytes),
        "source_refs": request.source_refs,
    }
    audit_log_path = append_audit_record(audit_root, audit_record)

    print(str(note_path))
    print(str(audit_log_path))
    return 0


def main() -> int:
    args = parse_args()
    try:
        if args.command != ALLOWED_OPERATION:
            raise WriterError(f"unsupported operation: {args.command}")
        return perform_inbox_write(args)
    except WriterError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
