"""Read-only vault reader for Phase 5 — Vault Conversational Read Chat MVP.

Reads note metadata and body excerpts from:
  - Agent/Inbox_Agent/
  - Agent/Reports_Agent/

Strategy:
  - list_last_n:      sort all notes by filename timestamp, return first n.
  - search_notes:     case-insensitive substring in (title + excerpt).
  - summarize_today:  filename prefix YYYYMMDD == today UTC + frontmatter check.

All operations are read-only. No vault mutations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

INBOX_DIR = "Agent/Inbox_Agent"
REPORTS_DIR = "Agent/Reports_Agent"
READ_DIRS: tuple[str, ...] = (INBOX_DIR, REPORTS_DIR)

# Match any timestamp-prefixed note: YYYYMMDDTHHMMSSZ_*.md
_ANY_NOTE_PAT = re.compile(r"^\d{8}T\d{6}Z_.+\.md$")
# Strip markdown headings / emphasis for clean text
_MD_HEADING = re.compile(r"^#{1,6}\s+")
_MD_EMPHASIS = re.compile(r"\*{1,2}([^*]+)\*{1,2}")

EXCERPT_MAX_CHARS = 200
DEFAULT_LAST_N = 5
MAX_LAST_N = 10
MAX_SEARCH_RESULTS = 8


@dataclass(frozen=True)
class NoteInfo:
    note_name: str
    source_dir: str          # e.g. "Agent/Inbox_Agent"
    run_id: str
    capture_status: str
    created_at_utc: str
    updated_at_utc: str
    title: str
    excerpt: str             # first EXCERPT_MAX_CHARS of plain body text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Extract key→value pairs from YAML-like frontmatter.  Returns {} on error."""
    try:
        content = path.read_text(encoding="utf-8")
        fields: dict[str, str] = {}
        in_fm = False
        for line in content.splitlines():
            s = line.strip()
            if s == "---":
                if not in_fm:
                    in_fm = True
                    continue
                break
            if in_fm and ":" in s:
                k, _, v = s.partition(":")
                fields[k.strip()] = v.strip().strip('"')
        return fields
    except Exception:
        return {}


def _plain_body_text(path: Path) -> str:
    """Return body text after frontmatter, stripped of basic markdown syntax."""
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        fm_end = 0
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    fm_end = i + 1
                    break
        parts: list[str] = []
        for line in lines[fm_end:]:
            s = line.strip()
            if not s:
                continue
            s = _MD_HEADING.sub("", s)
            s = _MD_EMPHASIS.sub(r"\1", s)
            if s:
                parts.append(s)
        return " ".join(parts)
    except Exception:
        return ""


def _first_heading(path: Path) -> str:
    """Return the first top-level heading (# ...) from the note body."""
    try:
        content = path.read_text(encoding="utf-8")
        fm_passed = False
        in_fm = False
        for line in content.splitlines():
            s = line.strip()
            if s == "---":
                if not in_fm:
                    in_fm = True
                else:
                    fm_passed = True
                continue
            if fm_passed and s.startswith("# ") and not s.startswith("## "):
                return s[2:].strip()
    except Exception:
        pass
    return ""


def _extract_title(path: Path, fm: dict[str, str]) -> str:
    t = fm.get("capture_title") or fm.get("title") or _first_heading(path)
    return t if t else path.stem


def _sorted_entries(vault_root: str, dirs: tuple[str, ...]) -> list[tuple[Path, str]]:
    """All note files across dirs, sorted newest-first by filename."""
    entries: list[tuple[Path, str]] = []
    for d in dirs:
        p = Path(vault_root) / d
        if not p.is_dir():
            continue
        for f in p.iterdir():
            if f.is_file() and _ANY_NOTE_PAT.match(f.name):
                entries.append((f, d))
    entries.sort(key=lambda x: x[0].name, reverse=True)
    return entries


def _build(path: Path, src_dir: str) -> NoteInfo | None:
    try:
        fm = _parse_frontmatter(path)
        title = _extract_title(path, fm)
        body = _plain_body_text(path)
        return NoteInfo(
            note_name=path.name,
            source_dir=src_dir,
            run_id=fm.get("run_id", "?"),
            capture_status=fm.get("capture_status", "?"),
            created_at_utc=fm.get("created_at_utc", "?"),
            updated_at_utc=fm.get("updated_at_utc", "?"),
            title=title,
            excerpt=body[:EXCERPT_MAX_CHARS],
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_last_n(
    vault_root: str,
    n: int,
    dirs: tuple[str, ...] = READ_DIRS,
) -> list[NoteInfo]:
    """Return up to n most recent notes across dirs, newest-first."""
    n = max(1, min(n, MAX_LAST_N))
    entries = _sorted_entries(vault_root, dirs)
    results: list[NoteInfo] = []
    for path, src in entries:
        if len(results) >= n:
            break
        info = _build(path, src)
        if info:
            results.append(info)
    return results


def search_notes(
    vault_root: str,
    query: str,
    dirs: tuple[str, ...] = READ_DIRS,
    max_results: int = MAX_SEARCH_RESULTS,
) -> list[NoteInfo]:
    """Case-insensitive substring search in (title + excerpt).  Returns newest-first."""
    q = query.lower().strip()
    if not q:
        return []
    entries = _sorted_entries(vault_root, dirs)
    results: list[NoteInfo] = []
    for path, src in entries:
        info = _build(path, src)
        if info is None:
            continue
        haystack = (info.title + " " + info.excerpt).lower()
        if q in haystack:
            results.append(info)
            if len(results) >= max_results:
                break
    return results


def summarize_today(
    vault_root: str,
    dirs: tuple[str, ...] = READ_DIRS,
) -> list[NoteInfo]:
    """Return notes whose filename prefix YYYYMMDD matches today (UTC)."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    entries = _sorted_entries(vault_root, dirs)
    results: list[NoteInfo] = []
    for path, src in entries:
        if not path.name.startswith(today_prefix):
            continue
        info = _build(path, src)
        if info:
            results.append(info)
    return results
