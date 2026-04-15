"""Read-only helpers for resolving Obsidian inbox note references.

Used by the Phase 4 conversational layer to resolve note references:
- "ultima" / "last"          → newest note by filename timestamp
- exact filename             → direct lookup in Agent/Inbox_Agent/
- run_id token               → substring search in filenames

All operations are read-only.  No vault mutations.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# vault_draft_promote_bridge is one level up (scripts/agents/openclaw/)
_BRIDGE_DIR = Path(__file__).resolve().parent
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from vault_draft_promote_bridge import INBOX_NOTE_PATTERN  # noqa: E402

INBOX_DIR = "Agent/Inbox_Agent"
_LAST_REF_TOKENS = frozenset({"ultima", "last", "la ultima", "la última", "última"})
_TOKEN_SAFE = re.compile(r"[^a-z0-9.\-]")
_ALNUM_ONLY = re.compile(r"[^a-z0-9]")  # for fuzzy filename comparison


@dataclass(frozen=True)
class ResolveResult:
    note_name: str
    run_id: str
    capture_status: str
    ambiguous: bool = False
    candidates: tuple[str, ...] = field(default_factory=tuple)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(note_path: Path) -> dict[str, str]:
    """Extract key→value pairs from YAML-like frontmatter.  Returns {} on any error."""
    try:
        content = note_path.read_text(encoding="utf-8")
        fields: dict[str, str] = {}
        in_fm = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "---":
                if not in_fm:
                    in_fm = True
                    continue
                break
            if in_fm and ":" in stripped:
                key, _, raw = stripped.partition(":")
                fields[key.strip()] = raw.strip().strip('"')
        return fields
    except Exception:
        return {}


def _inbox_notes_newest_first(vault_root: str) -> list[Path]:
    inbox_dir = Path(vault_root) / INBOX_DIR
    if not inbox_dir.is_dir():
        return []
    return sorted(
        (f for f in inbox_dir.iterdir() if f.is_file() and INBOX_NOTE_PATTERN.match(f.name)),
        key=lambda f: f.name,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_note(vault_root: str, note_ref: str) -> ResolveResult | None:
    """Resolve a note reference to a concrete inbox entry.

    Resolution order:
    1. "ultima" / "last"  → newest by filename.
    2. Exact filename matching INBOX_NOTE_PATTERN → direct lookup.
    3. Otherwise → case-insensitive token search in filenames.

    Returns:
    - None if vault inaccessible or inbox has no notes.
    - ResolveResult with capture_status="not_found" if ref looks like a filename but file is missing.
    - ResolveResult with ambiguous=True and candidates populated if multiple files match.
    """
    all_notes = _inbox_notes_newest_first(vault_root)
    if not all_notes:
        return None

    ref = note_ref.strip()
    ref_lower = ref.lower()

    # --- "la ultima" / "last" ---
    if ref_lower in _LAST_REF_TOKENS:
        path = all_notes[0]
        fm = _parse_frontmatter(path)
        return ResolveResult(
            note_name=path.name,
            run_id=fm.get("run_id", "?"),
            capture_status=fm.get("capture_status", "?"),
        )

    # --- exact filename ---
    if INBOX_NOTE_PATTERN.match(ref):
        candidate = Path(vault_root) / INBOX_DIR / ref
        if candidate.is_file():
            fm = _parse_frontmatter(candidate)
            return ResolveResult(
                note_name=ref,
                run_id=fm.get("run_id", "?"),
                capture_status=fm.get("capture_status", "?"),
            )
        return ResolveResult(note_name=ref, run_id="?", capture_status="not_found")

    # --- token search (alphanumeric normalization on both sides) ---
    # Note: input may come from Telegram text where hyphens are stripped to spaces
    # by _normalize_text.  We compare using alphanumeric-only strings so that
    # "tg001" (from "tg-001" normalized) matches "tg-001" in filenames.
    token = _ALNUM_ONLY.sub("", ref_lower)
    if not token:
        return None

    matches = [p for p in all_notes if token in _ALNUM_ONLY.sub("", p.name.lower())]
    if not matches:
        return None
    if len(matches) == 1:
        fm = _parse_frontmatter(matches[0])
        return ResolveResult(
            note_name=matches[0].name,
            run_id=fm.get("run_id", "?"),
            capture_status=fm.get("capture_status", "?"),
        )
    # Ambiguous — return up to 5 candidates
    return ResolveResult(
        note_name="",
        run_id="",
        capture_status="ambiguous",
        ambiguous=True,
        candidates=tuple(p.name for p in matches[:5]),
    )


def get_note_status(vault_root: str, note_name: str) -> dict[str, Any] | None:
    """Return status fields for a specific inbox note, or None if not found."""
    candidate = Path(vault_root) / INBOX_DIR / note_name
    if not candidate.is_file():
        return None
    fm = _parse_frontmatter(candidate)
    return {
        "note_name": note_name,
        "run_id": fm.get("run_id", "?"),
        "capture_status": fm.get("capture_status", "?"),
        "created_at_utc": fm.get("created_at_utc", "?"),
    }
