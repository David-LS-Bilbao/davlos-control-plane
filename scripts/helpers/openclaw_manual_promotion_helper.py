#!/usr/bin/env python3
"""Prepare and validate canonical manual handoff inputs for OpenClaw writers."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWED_SCHEMA_VERSION = 1
MAX_COMPONENT_LEN = 64
MAX_TITLE_BYTES = 160
MAX_BODY_BYTES = 24 * 1024


class HelperError(RuntimeError):
    """Raised when the manual promotion helper must stop for safety reasons."""


@dataclass(frozen=True)
class DomainSpec:
    name: str
    operation: str
    title_key: str
    output_name: str
    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...]
    external_dir_name: str | None = None
    relative_parent: Path | None = None


DOMAIN_SPECS: dict[str, DomainSpec] = {
    "inbox": DomainSpec(
        name="inbox",
        operation="inbox.write",
        title_key="capture_title",
        output_name="INBOX_INPUT.md",
        required_keys=("operation", "schema_version", "run_id", "capture_title"),
        optional_keys=("source_refs",),
        external_dir_name="openclaw-vault-inbox-writer",
    ),
    "draft": DomainSpec(
        name="draft",
        operation="draft.write",
        title_key="draft_title",
        output_name="STAGED_INPUT.md",
        required_keys=("operation", "schema_version", "run_id", "draft_title"),
        optional_keys=("source_refs", "proposed_target_path"),
        relative_parent=Path("Agent/Inbox_Agent"),
    ),
    "report": DomainSpec(
        name="report",
        operation="report.write",
        title_key="report_title",
        output_name="REPORT_INPUT.md",
        required_keys=("operation", "schema_version", "run_id", "report_title"),
        optional_keys=("source_refs",),
        external_dir_name="openclaw-vault-report-writer",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or validate canonical manual handoff inputs for inbox.write, "
            "draft.write and report.write without executing any writer."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("domain", choices=sorted(DOMAIN_SPECS))
    prepare_parser.add_argument("--output-file", required=True)
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--title", required=True)
    prepare_parser.add_argument("--body", required=True)
    prepare_parser.add_argument("--source-ref", action="append", default=[])
    prepare_parser.add_argument("--proposed-target-path", default="")
    prepare_parser.add_argument("--overwrite-existing", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("domain", choices=sorted(DOMAIN_SPECS))
    validate_parser.add_argument("--input-file", required=True)

    return parser.parse_args()


def sanitize_component(value: str, label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise HelperError(f"{label} is empty after sanitization")
    if len(cleaned) > MAX_COMPONENT_LEN:
        raise HelperError(f"{label} exceeds {MAX_COMPONENT_LEN} characters")
    if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise HelperError(f"{label} contains invalid path content")
    return cleaned


def sanitize_single_line_text(value: str, label: str, *, max_bytes: int) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise HelperError(f"{label} contains invalid control characters")
    cleaned = value.strip()
    if not cleaned:
        raise HelperError(f"{label} cannot be empty")
    if len(cleaned.encode("utf-8")) > max_bytes:
        raise HelperError(f"{label} exceeds {max_bytes} bytes")
    return cleaned


def sanitize_body_text(value: str, label: str, *, max_bytes: int) -> str:
    if "\x00" in value:
        raise HelperError(f"{label} contains invalid control characters")
    cleaned = value.strip()
    if not cleaned:
        raise HelperError(f"{label} cannot be empty")
    if len(cleaned.encode("utf-8")) > max_bytes:
        raise HelperError(f"{label} exceeds {max_bytes} bytes")
    return cleaned


def sanitize_source_refs(values: list[str]) -> list[str]:
    sanitized: list[str] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            raise HelperError("source_refs contains an empty value")
        if "\x00" in value or "\n" in value or "\r" in value:
            raise HelperError("source_refs contains invalid control characters")
        sanitized.append(value)
    return sanitized


def sanitize_optional_text(value: str, label: str, *, max_bytes: int = 512) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise HelperError(f"{label} contains invalid control characters")
    cleaned = value.strip()
    if len(cleaned.encode("utf-8")) > max_bytes:
        raise HelperError(f"{label} exceeds {max_bytes} bytes")
    return cleaned


def ensure_existing_directory(path: Path, label: str) -> None:
    try:
        path_lstat = path.lstat()
    except FileNotFoundError as exc:
        raise HelperError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(path_lstat.st_mode):
        raise HelperError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISDIR(path_lstat.st_mode):
        raise HelperError(f"{label} must be a directory: {path}")


def ensure_existing_file(path: Path, label: str) -> None:
    try:
        path_lstat = path.lstat()
    except FileNotFoundError as exc:
        raise HelperError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(path_lstat.st_mode):
        raise HelperError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(path_lstat.st_mode):
        raise HelperError(f"{label} must be a regular file: {path}")


def assert_no_symlinks(path: Path, label: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        try:
            path_lstat = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(path_lstat.st_mode):
            raise HelperError(f"{label} contains a symlink component: {current}")


def split_frontmatter(document_text: str) -> tuple[list[str], str]:
    lines = document_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise HelperError("input file must start with frontmatter delimiter ---")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise HelperError("input file is missing closing frontmatter delimiter ---")
    return lines[1:closing_index], "\n".join(lines[closing_index + 1 :])


def parse_frontmatter_scalar(raw_value: str, label: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise HelperError(f"{label} is not valid JSON string syntax") from exc
        if not isinstance(parsed, str):
            raise HelperError(f"{label} must decode to a string")
        return parsed
    return value


def parse_frontmatter_int(raw_value: str, label: str) -> int:
    value = raw_value.strip()
    if not re.fullmatch(r"[0-9]+", value):
        raise HelperError(f"{label} must be an integer")
    return int(value)


def parse_frontmatter_string_list(raw_value: str, label: str) -> list[str]:
    value = raw_value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HelperError(f"{label} must use inline JSON array syntax") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise HelperError(f"{label} must be a list of strings")
    return sanitize_source_refs(parsed)


def validate_output_path(path_str: str, spec: DomainSpec) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        raise HelperError("output-file must be an absolute path")
    assert_no_symlinks(candidate, "output-file")
    if candidate.suffix.lower() != ".md":
        raise HelperError("output-file must end with .md")
    if candidate.name != spec.output_name:
        raise HelperError(f"output-file must use the canonical name {spec.output_name}")
    if spec.external_dir_name is not None:
        if candidate.parent.name != spec.external_dir_name:
            raise HelperError("output-file must live directly in the canonical external directory")
    if spec.relative_parent is not None:
        expected_suffix = spec.relative_parent / spec.output_name
        if list(candidate.parts[-len(expected_suffix.parts):]) != list(expected_suffix.parts):
            raise HelperError(f"output-file must end with {expected_suffix}")
    ensure_existing_directory(candidate.parent, "output-file parent")
    return candidate


def build_document(
    spec: DomainSpec,
    *,
    run_id: str,
    title: str,
    body: str,
    source_refs: list[str],
    proposed_target_path: str,
) -> str:
    lines = [
        "---",
        f"operation: {spec.operation}",
        f"schema_version: {ALLOWED_SCHEMA_VERSION}",
        f'run_id: "{run_id}"',
        f'{spec.title_key}: {json.dumps(title, ensure_ascii=True)}',
    ]
    if source_refs:
        lines.append(f"source_refs: {json.dumps(source_refs, ensure_ascii=True)}")
    if spec.name == "draft":
        lines.append(
            f"proposed_target_path: {json.dumps(proposed_target_path, ensure_ascii=True)}"
        )
    lines.extend(["---", "", body, ""])
    return "\n".join(lines)


def parse_and_validate_document(spec: DomainSpec, document_text: str) -> dict[str, object]:
    frontmatter_lines, body_text = split_frontmatter(document_text)
    raw_fields: dict[str, str] = {}

    allowed_keys = set(spec.required_keys) | set(spec.optional_keys)
    for line_number, line in enumerate(frontmatter_lines, start=2):
        if not line.strip():
            raise HelperError(f"frontmatter line {line_number} must not be empty")
        if ":" not in line:
            raise HelperError(f"frontmatter line {line_number} is missing ':'")
        key, raw_value = line.split(":", 1)
        normalized_key = key.strip()
        if normalized_key not in allowed_keys:
            raise HelperError(f"frontmatter key is not allowed: {normalized_key}")
        if normalized_key in raw_fields:
            raise HelperError(f"frontmatter key is duplicated: {normalized_key}")
        raw_fields[normalized_key] = raw_value

    missing = sorted(set(spec.required_keys) - raw_fields.keys())
    if missing:
        raise HelperError(
            "input file is missing required frontmatter keys: " + ", ".join(missing)
        )

    operation = parse_frontmatter_scalar(raw_fields["operation"], "operation")
    if operation != spec.operation:
        raise HelperError(f"operation must be {spec.operation}")
    schema_version = parse_frontmatter_int(raw_fields["schema_version"], "schema_version")
    if schema_version != ALLOWED_SCHEMA_VERSION:
        raise HelperError(f"schema_version must be {ALLOWED_SCHEMA_VERSION}")
    run_id = sanitize_component(
        parse_frontmatter_scalar(raw_fields["run_id"], "run_id"),
        "run_id",
    )
    title = sanitize_single_line_text(
        parse_frontmatter_scalar(raw_fields[spec.title_key], spec.title_key),
        spec.title_key,
        max_bytes=MAX_TITLE_BYTES,
    )
    source_refs = parse_frontmatter_string_list(raw_fields.get("source_refs", ""), "source_refs")
    body = sanitize_body_text(body_text, "body", max_bytes=MAX_BODY_BYTES)
    proposed_target_path = sanitize_optional_text(
        parse_frontmatter_scalar(raw_fields.get("proposed_target_path", ""), "proposed_target_path"),
        "proposed_target_path",
    )
    if spec.name != "draft" and proposed_target_path:
        raise HelperError("proposed_target_path is only allowed for draft")
    return {
        "domain": spec.name,
        "operation": operation,
        "schema_version": schema_version,
        "run_id": run_id,
        "title": title,
        "source_refs": source_refs,
        "body_bytes": len(body.encode("utf-8")),
        "proposed_target_path": proposed_target_path,
    }


def write_document(path: Path, content: str, *, overwrite_existing: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite_existing else os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = None
    try:
        fd = os.open(path, flags | nofollow, 0o660)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = None
            handle.write(content)
    except FileExistsError as exc:
        raise HelperError(f"output-file already exists: {path}") from exc
    except OSError as exc:
        raise HelperError(f"failed to write output-file: {path}: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def prepare_input(args: argparse.Namespace) -> int:
    spec = DOMAIN_SPECS[args.domain]
    output_path = validate_output_path(args.output_file, spec)
    run_id = sanitize_component(args.run_id, "run_id")
    title = sanitize_single_line_text(args.title, "title", max_bytes=MAX_TITLE_BYTES)
    body = sanitize_body_text(args.body, "body", max_bytes=MAX_BODY_BYTES)
    source_refs = sanitize_source_refs(args.source_ref)
    proposed_target_path = sanitize_optional_text(
        args.proposed_target_path,
        "proposed_target_path",
    )
    if spec.name != "draft" and proposed_target_path:
        raise HelperError("proposed_target_path is only supported for draft")

    document_text = build_document(
        spec,
        run_id=run_id,
        title=title,
        body=body,
        source_refs=source_refs,
        proposed_target_path=proposed_target_path,
    )
    parse_and_validate_document(spec, document_text)
    write_document(output_path, document_text, overwrite_existing=args.overwrite_existing)
    print(
        json.dumps(
            {
                "command": "prepare",
                "domain": spec.name,
                "operation": spec.operation,
                "output_file": str(output_path),
                "overwrite_existing": bool(args.overwrite_existing),
                "source_refs_count": len(source_refs),
            },
            sort_keys=True,
        )
    )
    return 0


def validate_input(args: argparse.Namespace) -> int:
    spec = DOMAIN_SPECS[args.domain]
    input_path = validate_output_path(args.input_file, spec)
    ensure_existing_file(input_path, "input-file")
    content = input_path.read_text(encoding="utf-8")
    result = parse_and_validate_document(spec, content)
    result["command"] = "validate"
    result["input_file"] = str(input_path)
    print(json.dumps(result, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    try:
        if args.command == "prepare":
            return prepare_input(args)
        if args.command == "validate":
            return validate_input(args)
        raise HelperError(f"unsupported command: {args.command}")
    except HelperError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
