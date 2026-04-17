"""Read-only vault browsing for E1 (note content) and E2 (folder exploration).

No mutations. All operations are read-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Directories excluded from public listing/creation (pipeline-reserved)
_EXCLUDED_DIRS: frozenset[str] = frozenset({"Agent", ".obsidian", ".git"})
_HIDDEN_PATTERN = re.compile(r"^\.")
# Pipeline artifact files — excluded from note listings and search results
_PIPELINE_FILES: frozenset[str] = frozenset({"STAGED_INPUT.md", "REPORT_INPUT.md"})

MAX_CONTENT_LINES = 60


@dataclass(frozen=True)
class NoteContent:
    note_name: str
    rel_path: str          # relative to vault_root
    content: str           # body text, possibly truncated
    truncated: bool
    total_lines: int


@dataclass(frozen=True)
class VaultSection:
    name: str
    rel_path: str
    note_count: int


def list_vault_sections(vault_root: str) -> list[VaultSection]:
    """List top-level directories in the vault (excludes hidden and reserved)."""
    root = Path(vault_root)
    if not root.is_dir():
        return []
    sections = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in _EXCLUDED_DIRS:
            continue
        if _HIDDEN_PATTERN.match(entry.name):
            continue
        count = sum(1 for f in entry.rglob("*.md") if f.is_file() and f.name not in _PIPELINE_FILES)
        sections.append(VaultSection(name=entry.name, rel_path=entry.name, note_count=count))
    return sections


def resolve_vault_section(vault_root: str, folder_ref: str) -> str | None:
    """Fuzzy-resolve a folder name to an existing section rel_path.

    Example: "Proyectos" → "10_Proyectos"
    Returns rel_path string or None if not found.
    """
    root = Path(vault_root)
    ref_norm = _normalize_name(folder_ref)
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in _EXCLUDED_DIRS or _HIDDEN_PATTERN.match(entry.name):
            continue
        if ref_norm in _normalize_name(entry.name) or _normalize_name(entry.name) in ref_norm:
            return entry.name
    return None


def list_notes_in_section(vault_root: str, folder_rel: str) -> list[str]:
    """List .md note names directly inside a vault section (one level deep)."""
    root = Path(vault_root).resolve()
    target = (root / folder_rel).resolve()
    if not str(target).startswith(str(root)):
        return []
    if not target.is_dir():
        return []
    return sorted(
        f.name for f in target.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name not in _PIPELINE_FILES
    )


def find_note_anywhere(vault_root: str, note_ref: str) -> list[tuple[str, Path]]:
    """Search all .md files in vault for a filename match.

    Returns list of (rel_path, Path) tuples, up to 10 matches.
    """
    root = Path(vault_root).resolve()
    if not root.is_dir():
        return []
    # Also try matching without .md extension so "demo.md" finds "demo.md"
    ref_stripped = note_ref[:-3] if note_ref.lower().endswith(".md") else note_ref
    ref_norm = _normalize_name(ref_stripped)
    matches: list[tuple[str, Path]] = []
    for md_file in sorted(root.rglob("*.md")):
        name_norm = _normalize_name(md_file.stem)
        if ref_norm in name_norm or name_norm.startswith(ref_norm):
            try:
                rel = str(md_file.relative_to(root))
            except ValueError:
                continue
            matches.append((rel, md_file))
            if len(matches) >= 10:
                break
    return matches


def read_note_content(
    vault_root: str,
    note_rel_path: str,
    *,
    max_lines: int = MAX_CONTENT_LINES,
) -> NoteContent | None:
    """Read a note's content by relative path within vault.

    Returns None if path is invalid or resolves outside vault.
    Security: enforces that resolved path stays inside vault_root.
    """
    root = Path(vault_root).resolve()
    target = (root / note_rel_path).resolve()
    if not str(target).startswith(str(root) + "/") and target != root:
        return None
    if not target.is_file():
        return None
    try:
        raw = target.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    lines = raw.splitlines()
    total = len(lines)
    truncated = total > max_lines
    content = "\n".join(lines[:max_lines])
    try:
        rel_path = str(target.relative_to(root))
    except ValueError:
        rel_path = note_rel_path
    return NoteContent(
        note_name=target.name,
        rel_path=rel_path,
        content=content,
        truncated=truncated,
        total_lines=total,
    )


def search_vault_broad(
    vault_root: str,
    query: str,
    *,
    max_results: int = 6,
    excerpt_chars: int = 120,
) -> list[tuple[str, str]]:
    """Search all .md files across vault for query in filename or content.

    Returns list of (rel_path, excerpt) tuples.
    Excludes Agent/, .obsidian/, .git/.
    """
    root = Path(vault_root).resolve()
    if not root.is_dir() or not query.strip():
        return []
    q = query.lower().strip()
    matches: list[tuple[str, str]] = []
    seen: set[str] = set()
    for md_file in sorted(root.rglob("*.md")):
        # skip reserved dirs and pipeline artifacts
        try:
            parts = md_file.relative_to(root).parts
        except ValueError:
            continue
        if parts and parts[0] in _EXCLUDED_DIRS:
            continue
        if md_file.name in _PIPELINE_FILES:
            continue
        try:
            rel = str(md_file.relative_to(root))
        except ValueError:
            continue
        if rel in seen:
            continue
        # match in filename first (cheap)
        if q in md_file.name.lower():
            excerpt = _first_excerpt(md_file, excerpt_chars)
            matches.append((rel, excerpt))
            seen.add(rel)
            if len(matches) >= max_results:
                break
            continue
        # match in content (more expensive)
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if q in content.lower():
            excerpt = _first_excerpt(md_file, excerpt_chars, content=content)
            matches.append((rel, excerpt))
            seen.add(rel)
            if len(matches) >= max_results:
                break
    return matches


def _first_excerpt(path: Path, chars: int, *, content: str | None = None) -> str:
    """Return first non-frontmatter, non-heading lines as a short excerpt."""
    try:
        raw = content if content is not None else path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    in_frontmatter = False
    fragments: list[str] = []
    total = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        fragments.append(stripped)
        total += len(stripped)
        if total >= chars:
            break
    excerpt = " ".join(fragments)
    return excerpt[:chars] + ("…" if len(excerpt) > chars else "")


def _normalize_name(text: str) -> str:
    """Lower, strip digits-prefix, remove separators for fuzzy matching."""
    t = text.lower().strip()
    t = re.sub(r"^\d+[_\-]", "", t)   # strip numeric prefix like "10_"
    t = re.sub(r"[_\-\s]", "", t)
    return t
