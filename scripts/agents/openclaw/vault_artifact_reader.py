"""Read-only inspection of pending pipeline artifacts.

Reads the presence and first-line metadata of STAGED_INPUT.md and
REPORT_INPUT.md from the vault inbox directory.  Never mutates either file.

Used by Phase 6 — Operational Hygiene and Conversational UX MVP.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

STAGED_FILENAME = "STAGED_INPUT.md"
REPORT_FILENAME = "REPORT_INPUT.md"
INBOX_DIR = "Agent/Inbox_Agent"

# Frontmatter keys that may record the source note name
_SOURCE_KEY_CANDIDATES = ("note_name", "source_note", "inbox_note")


@dataclass(frozen=True)
class ArtifactStatus:
    staged_exists: bool
    report_exists: bool
    staged_note_name: str  # extracted from STAGED_INPUT.md frontmatter, or ""
    report_note_name: str  # extracted from REPORT_INPUT.md frontmatter, or ""


def _extract_note_name(path: Path) -> str:
    """Try to extract the source note name from a pipeline artifact's frontmatter.

    Returns "" on any error or if the key is absent.
    """
    try:
        content = path.read_text(encoding="utf-8")
        in_fm = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "---":
                if not in_fm:
                    in_fm = True
                    continue
                break  # end of frontmatter
            if not in_fm:
                continue
            for key in _SOURCE_KEY_CANDIDATES:
                if stripped.startswith(key + ":"):
                    _, _, raw = stripped.partition(":")
                    return raw.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def read_pending_artifacts(vault_root: str) -> ArtifactStatus:
    """Return the presence status of STAGED_INPUT.md and REPORT_INPUT.md.

    This is a purely read-only operation.  Neither file is mutated or deleted.
    """
    inbox = Path(vault_root) / INBOX_DIR
    staged_path = inbox / STAGED_FILENAME
    report_path = inbox / REPORT_FILENAME

    staged_exists = staged_path.is_file()
    report_exists = report_path.is_file()

    return ArtifactStatus(
        staged_exists=staged_exists,
        report_exists=report_exists,
        staged_note_name=_extract_note_name(staged_path) if staged_exists else "",
        report_note_name=_extract_note_name(report_path) if report_exists else "",
    )
