"""Tests for Phase 8 — Full Vault CRUD.

Covers:
E1 — Read note content from anywhere in vault
E2 — List vault sections and notes in a section
E3 — Create notes in any non-reserved folder (mutation + confirmation)
E4 — Archive notes to 50_Archivado (mutation + confirmation)
vault_browser module: list_vault_sections, list_notes_in_section,
                      find_note_anywhere, read_note_content, resolve_vault_section
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_OPENCLAW = Path(__file__).resolve().parents[2] / "scripts" / "agents" / "openclaw"
_RO = _OPENCLAW / "restricted_operator"

if str(_OPENCLAW) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW))
if str(_RO) not in sys.path:
    sys.path.insert(0, str(_RO))

import assistant_responses  # noqa: E402
from vault_browser import (  # noqa: E402
    find_note_anywhere,
    list_notes_in_section,
    list_vault_sections,
    read_note_content,
    resolve_vault_section,
)
from telegram_bot import TelegramCommandProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(root: Path, *, sections: list[str] | None = None) -> Path:
    vault = root / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    default_sections = sections or [
        "00_Inbox", "10_Proyectos", "20_Areas", "50_Archivado", "Agent"
    ]
    for sec in default_sections:
        (vault / sec).mkdir(exist_ok=True)
    (vault / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
    return vault


def _write_note(path: Path, *, title: str = "Test", body: str = "Body.") -> Path:
    path.write_text(
        f"---\ntitle: \"{title}\"\n---\n\n# {title}\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _make_policy(root: Path, *, vault_root: str = "") -> Path:
    policy = {
        "broker": {
            "bind_host": "127.0.0.1", "bind_port": 18899,
            "audit_log_path": str(root / "audit.jsonl"),
            "state_store_path": str(root / "state.json"),
            "dropzone_dir": str(root / "dropzone"),
            "max_tail_lines": 20, "max_write_bytes": 4096,
        },
        "vault_inbox": {"vault_root": vault_root},
        "actions": {
            "action.inbox.write.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "inbox write",
            },
            "action.draft.promote.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "draft promote",
            },
            "action.report.promote.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "report promote",
            },
            "action.logs.read.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.read", "description": "logs read",
            },
            "action.note.create.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "note create",
            },
            "action.note.archive.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "note archive",
            },
        },
        "log_streams": {}, "health_checks": {}, "webhook_targets": {},
        "operator_auth": {
            "roles": {
                "viewer": ["policy.read"],
                "operator": ["policy.read", "operator.read", "operator.write", "operator.audit"],
            },
            "operators": {"op1": {"role": "operator", "active": True}},
        },
        "telegram": {
            "enabled": True, "api_base_url": "https://api.telegram.org",
            "bot_token_env": "TELEGRAM_BOT_TOKEN",
            "allowed_chats": {"100": {"principal_id": "p1", "operator_id": "op1"}},
            "allowed_users": {},
            "rate_limit_window_seconds": 60, "rate_limit_max_requests": 100,
            "max_command_length": 512, "poll_timeout_seconds": 30,
            "audit_tail_lines": 5,
            "offset_store_path": str(root / "offset.json"),
            "runtime_status_path": str(root / "status.json"),
            "assistant_idle_timeout_seconds": 300,
        },
    }
    path = root / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


def _make_proc(policy_path: str) -> TelegramCommandProcessor:
    return TelegramCommandProcessor(policy_path=policy_path, api_client=MagicMock())


# ---------------------------------------------------------------------------
# vault_browser — list_vault_sections
# ---------------------------------------------------------------------------

class TestListVaultSections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sections_listed(self):
        sections = list_vault_sections(str(self.vault))
        names = [s.name for s in sections]
        self.assertIn("10_Proyectos", names)
        self.assertIn("20_Areas", names)

    def test_agent_excluded(self):
        sections = list_vault_sections(str(self.vault))
        names = [s.name for s in sections]
        self.assertNotIn("Agent", names)

    def test_note_count(self):
        _write_note(self.vault / "10_Proyectos" / "note1.md", title="N1")
        _write_note(self.vault / "10_Proyectos" / "note2.md", title="N2")
        sections = list_vault_sections(str(self.vault))
        p = next(s for s in sections if s.name == "10_Proyectos")
        self.assertEqual(p.note_count, 2)

    def test_empty_vault_root(self):
        result = list_vault_sections("/nonexistent/vault")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# vault_browser — resolve_vault_section
# ---------------------------------------------------------------------------

class TestResolveVaultSection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_match(self):
        result = resolve_vault_section(str(self.vault), "10_Proyectos")
        self.assertEqual(result, "10_Proyectos")

    def test_fuzzy_no_prefix(self):
        result = resolve_vault_section(str(self.vault), "Proyectos")
        self.assertEqual(result, "10_Proyectos")

    def test_fuzzy_case_insensitive(self):
        result = resolve_vault_section(str(self.vault), "proyectos")
        self.assertEqual(result, "10_Proyectos")

    def test_not_found_returns_none(self):
        result = resolve_vault_section(str(self.vault), "Nonexistent")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# vault_browser — list_notes_in_section
# ---------------------------------------------------------------------------

class TestListNotesInSection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_lists_md_notes(self):
        _write_note(self.vault / "10_Proyectos" / "Alpha.md", title="Alpha")
        _write_note(self.vault / "10_Proyectos" / "Beta.md", title="Beta")
        notes = list_notes_in_section(str(self.vault), "10_Proyectos")
        self.assertIn("Alpha.md", notes)
        self.assertIn("Beta.md", notes)

    def test_empty_section(self):
        notes = list_notes_in_section(str(self.vault), "20_Areas")
        self.assertEqual(notes, [])

    def test_traversal_blocked(self):
        notes = list_notes_in_section(str(self.vault), "../etc")
        self.assertEqual(notes, [])


# ---------------------------------------------------------------------------
# vault_browser — find_note_anywhere
# ---------------------------------------------------------------------------

class TestFindNoteAnywhere(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_note_in_subfolder(self):
        _write_note(self.vault / "10_Proyectos" / "MiPlan.md", title="Mi Plan")
        results = find_note_anywhere(str(self.vault), "MiPlan")
        self.assertEqual(len(results), 1)
        rel, _ = results[0]
        self.assertIn("MiPlan.md", rel)

    def test_fuzzy_partial_match(self):
        _write_note(self.vault / "20_Areas" / "Finanzas-2026.md", title="Finanzas")
        results = find_note_anywhere(str(self.vault), "Finanzas")
        self.assertGreater(len(results), 0)

    def test_no_match(self):
        results = find_note_anywhere(str(self.vault), "Nonexistent_xyz_123")
        self.assertEqual(results, [])

    def test_case_insensitive(self):
        _write_note(self.vault / "10_Proyectos" / "MyNote.md", title="My")
        results = find_note_anywhere(str(self.vault), "mynote")
        self.assertGreater(len(results), 0)


# ---------------------------------------------------------------------------
# vault_browser — read_note_content
# ---------------------------------------------------------------------------

class TestReadNoteContent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_content(self):
        _write_note(self.vault / "10_Proyectos" / "MyNote.md", title="T", body="Hello world")
        result = read_note_content(str(self.vault), "10_Proyectos/MyNote.md")
        self.assertIsNotNone(result)
        self.assertIn("Hello world", result.content)

    def test_truncation(self):
        body = "\n".join(f"line {i}" for i in range(100))
        _write_note(self.vault / "10_Proyectos" / "Big.md", body=body)
        result = read_note_content(str(self.vault), "10_Proyectos/Big.md", max_lines=10)
        self.assertTrue(result.truncated)
        self.assertEqual(result.total_lines, 106)  # 3 frontmatter + blank + title + blank + 100 body

    def test_traversal_returns_none(self):
        result = read_note_content(str(self.vault), "../etc/passwd")
        self.assertIsNone(result)

    def test_missing_file_returns_none(self):
        result = read_note_content(str(self.vault), "10_Proyectos/ghost.md")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# E1 — Intent matching and handler
# ---------------------------------------------------------------------------

class TestE1ReadContentIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_que_dice_intent(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("que dice MiNota", assistant_awake=True)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.read_content")
        self.assertEqual(intent["params"]["note_ref"], "minota")  # normalized: spaces removed

    def test_muestrame_nota(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("muestrame MiNota", assistant_awake=True)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.read_content")

    def test_muestrame_las_ultimas_not_caught_as_read(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("muestrame las ultimas 5 notas", assistant_awake=True)
        self.assertIsNotNone(intent)
        self.assertNotEqual(intent["intent"], "obsidian.read_content")
        self.assertEqual(intent["intent"], "obsidian.list_last_n")

    def test_handler_finds_note(self):
        _write_note(self.vault / "10_Proyectos" / "Alpha.md", title="Alpha", body="contenido de alpha")
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_read_content(
            operator_id="op1", note_ref="Alpha", chat_id="100", user_id="1"
        )
        self.assertIn("Alpha.md", reply)
        self.assertIn("contenido de alpha", reply)

    def test_handler_not_found(self):
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_read_content(
            operator_id="op1", note_ref="Nonexistent_xyz_999", chat_id="100", user_id="1"
        )
        self.assertIn("encontré", reply.lower())

    def test_handler_saves_session_note(self):
        _write_note(self.vault / "10_Proyectos" / "Alpha.md", title="Alpha", body="x")
        proc = _make_proc(str(self.policy_path))
        proc._obsidian_read_content(
            operator_id="op1", note_ref="Alpha", chat_id="100", user_id="1"
        )
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertIn("Alpha.md", resolved)


# ---------------------------------------------------------------------------
# E2 — Intent matching and handlers
# ---------------------------------------------------------------------------

class TestE2SectionsIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_que_carpetas_hay_intent(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("que carpetas hay", assistant_awake=False)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.list_sections")

    def test_que_hay_en_intent(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("que hay en Proyectos", assistant_awake=True)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.list_section_notes")
        self.assertEqual(intent["params"]["folder_ref"], "proyectos")

    def test_list_sections_handler(self):
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_list_sections(operator_id="op1")
        self.assertIn("10_Proyectos", reply)
        self.assertIn("nota(s)", reply)

    def test_list_section_notes_fuzzy(self):
        _write_note(self.vault / "10_Proyectos" / "Plan.md", title="Plan")
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_list_section_notes(operator_id="op1", folder_ref="Proyectos")
        self.assertIn("Plan.md", reply)

    def test_list_section_notes_not_found(self):
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_list_section_notes(operator_id="op1", folder_ref="Nonexistent_xyz")
        self.assertIn("No encontré", reply)


# ---------------------------------------------------------------------------
# E3 — NoteCreateAction + intent
# ---------------------------------------------------------------------------

class TestE3NoteCreate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_note_intent_detected(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent(
            "crea una nota en 10_Proyectos: Mi Plan :: Detalles del plan", assistant_awake=True
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.create_note")
        self.assertEqual(intent["params"]["folder"], "10_Proyectos")
        self.assertEqual(intent["params"]["title"], "Mi Plan")
        self.assertIn("Detalles", intent["params"]["body"])

    def test_create_note_action_creates_file(self):
        from actions import NoteCreateAction
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteCreateAction(policy)
        result = action.execute({
            "folder": "10_Proyectos",
            "title": "Mi Plan de Prueba",
            "body": "Contenido del plan.",
        })
        self.assertTrue(result.ok)
        note_name = result.result["note_name"]
        created_path = self.vault / "10_Proyectos" / note_name
        self.assertTrue(created_path.exists())
        content = created_path.read_text(encoding="utf-8")
        self.assertIn("Mi Plan de Prueba", content)

    def test_create_note_agent_folder_blocked(self):
        from actions import NoteCreateAction, ActionError
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteCreateAction(policy)
        with self.assertRaises(ActionError) as ctx:
            action.execute({"folder": "Agent", "title": "T", "body": "B"})
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_create_note_traversal_blocked(self):
        from actions import NoteCreateAction, ActionError
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteCreateAction(policy)
        with self.assertRaises(ActionError) as ctx:
            action.execute({"folder": "../etc", "title": "T", "body": "B"})
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_create_note_nonexistent_folder(self):
        from actions import NoteCreateAction, ActionError
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteCreateAction(policy)
        with self.assertRaises(ActionError) as ctx:
            action.execute({"folder": "99_NoExiste", "title": "T", "body": "B"})
        self.assertEqual(ctx.exception.code, "not_found")

    def test_create_note_confirmation_flow(self):
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_create_note(
            chat_id="100", user_id="1", operator_id="op1",
            folder="10_Proyectos", title="Test Note", body="body here",
            mode="conversation",
        )
        self.assertIn("si", reply.lower())
        # Confirm
        reply2 = proc.handle_text(chat_id="100", user_id="1", text="si")
        self.assertIn("Nota creada", reply2)


# ---------------------------------------------------------------------------
# E4 — NoteArchiveAction + intent
# ---------------------------------------------------------------------------

class TestE4NoteArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_archive_intent_detected(self):
        proc = _make_proc(str(self.policy_path))
        intent = proc._detect_conversational_intent("archiva MiNota", assistant_awake=True)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.archive_note")
        self.assertEqual(intent["params"]["note_ref"], "minota")

    def test_archive_action_moves_file(self):
        from actions import NoteArchiveAction, ActionError
        from policy import PolicyStore
        note = self.vault / "10_Proyectos" / "ToArchive.md"
        _write_note(note, title="ToArchive")
        policy = PolicyStore(str(self.policy_path))
        action = NoteArchiveAction(policy)
        result = action.execute({"note_path": "10_Proyectos/ToArchive.md"})
        self.assertTrue(result.ok)
        self.assertFalse(note.exists())
        dest = self.vault / "50_Archivado" / "ToArchive.md"
        self.assertTrue(dest.exists())

    def test_archive_action_note_not_found(self):
        from actions import NoteArchiveAction, ActionError
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteArchiveAction(policy)
        with self.assertRaises(ActionError) as ctx:
            action.execute({"note_path": "10_Proyectos/ghost.md"})
        self.assertEqual(ctx.exception.code, "not_found")

    def test_archive_traversal_blocked(self):
        from actions import NoteArchiveAction, ActionError
        from policy import PolicyStore
        policy = PolicyStore(str(self.policy_path))
        action = NoteArchiveAction(policy)
        with self.assertRaises(ActionError) as ctx:
            action.execute({"note_path": "../etc/passwd"})
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_archive_confirmation_flow(self):
        note = self.vault / "10_Proyectos" / "DeleteMe.md"
        _write_note(note, title="DeleteMe")
        proc = _make_proc(str(self.policy_path))
        reply = proc._obsidian_archive_note(
            chat_id="100", user_id="1", operator_id="op1",
            note_ref="DeleteMe", mode="conversation",
        )
        self.assertIn("si", reply.lower())
        reply2 = proc.handle_text(chat_id="100", user_id="1", text="si")
        self.assertIn("Archivada", reply2)
        self.assertFalse(note.exists())


# ---------------------------------------------------------------------------
# render functions
# ---------------------------------------------------------------------------

class TestPhase8Renders(unittest.TestCase):
    def test_render_vault_sections(self):
        from vault_browser import VaultSection
        sections = [
            VaultSection(name="10_Proyectos", rel_path="10_Proyectos", note_count=3),
            VaultSection(name="20_Areas", rel_path="20_Areas", note_count=0),
        ]
        result = assistant_responses.render_vault_sections(sections)
        self.assertIn("10_Proyectos", result)
        self.assertIn("3 nota(s)", result)

    def test_render_section_notes(self):
        result = assistant_responses.render_section_notes("10_Proyectos", ["A.md", "B.md"])
        self.assertIn("A.md", result)
        self.assertIn("10_Proyectos", result)

    def test_render_section_notes_empty(self):
        result = assistant_responses.render_section_notes("20_Areas", [])
        self.assertIn("No hay notas", result)

    def test_render_note_content(self):
        result = assistant_responses.render_note_content(
            "MyNote.md", "10_Proyectos/MyNote.md", "# Title\n\nHello.",
            truncated=False, total_lines=3,
        )
        self.assertIn("MyNote.md", result)
        self.assertIn("Hello.", result)

    def test_render_note_content_truncated(self):
        result = assistant_responses.render_note_content(
            "Big.md", "10_Proyectos/Big.md", "partial content",
            truncated=True, total_lines=200,
        )
        self.assertIn("200", result)

    def test_render_note_ambiguous(self):
        from pathlib import Path
        candidates = [
            ("10_Proyectos/Alpha.md", Path("...")),
            ("20_Areas/Alpha-v2.md", Path("...")),
        ]
        result = assistant_responses.render_note_ambiguous(candidates, "Alpha")
        self.assertIn("2 notas", result)
        self.assertIn("10_Proyectos/Alpha.md", result)

    def test_render_note_created(self):
        result = assistant_responses.render_note_created("20260415T100000Z_test.md", "10_Proyectos")
        self.assertIn("Nota creada", result)

    def test_render_note_archived(self):
        result = assistant_responses.render_note_archived(
            "Note.md", "10_Proyectos/Note.md", "50_Archivado/Note.md"
        )
        self.assertIn("Archivada", result)
        self.assertIn("50_Archivado", result)


if __name__ == "__main__":
    unittest.main()
