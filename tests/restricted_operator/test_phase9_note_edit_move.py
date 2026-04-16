"""Tests for Phase 9 E5/E6 — NoteEditAction and NoteMoveFolderAction.

Covers:
E5 — action.note.edit.v1 (append / replace)
E6 — action.note.move.v1
Conversational intents for edit and move
_execute_pending_confirmation branches for note_edit and note_move
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
from actions import NoteEditAction, NoteMoveFolderAction  # noqa: E402
from policy import PolicyStore  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    vault.mkdir()
    for d in ["10_Proyectos", "20_Areas", "50_Archivado", "Agent"]:
        (vault / d).mkdir()
    (vault / "Agent" / "Inbox_Agent").mkdir(parents=True)
    return vault


def _write_note(path: Path, *, content: str = "---\ntitle: \"Test\"\n---\n\n# Test\n\nBody.\n") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _make_policy(root: Path, *, vault_root: str = "") -> Path:
    p = root / "policy.json"
    p.write_text(json.dumps({
        "broker": {
            "bind_host": "127.0.0.1", "bind_port": 18890,
            "audit_log_path": str(root / "audit.jsonl"),
            "state_store_path": str(root / "state.json"),
            "dropzone_dir": str(root / "dropzone"),
            "max_tail_lines": 50, "max_write_bytes": 4096,
        },
        "vault_inbox": {"vault_root": vault_root},
        "actions": {
            "action.note.edit.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "edit note",
            },
            "action.note.move.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "move note",
            },
        },
        "operator_auth": {
            "roles": {
                "operator": ["policy.read", "policy.mutate", "operator.read",
                             "operator.trigger", "operator.write"],
            },
            "operators": {
                "test-operator": {
                    "role": "operator", "enabled": True,
                    "display_name": "Test", "reason": "test",
                },
            },
        },
        "telegram": {
            "enabled": True,
            "bot_token_env": "TELEGRAM_TEST_TOKEN",
            "api_base_url": "https://api.telegram.org",
            "poll_timeout_seconds": 20, "audit_tail_lines": 10,
            "offset_store_path": str(root / "offset.json"),
            "runtime_status_path": str(root / "runtime.json"),
            "rate_limit_window_seconds": 30, "rate_limit_max_requests": 60,
            "max_command_length": 512, "assistant_idle_timeout_seconds": 600,
            "allowed_chats": {
                "100": {
                    "operator_id": "test-operator", "enabled": True,
                    "display_name": "Test", "reason": "test",
                },
            },
            "allowed_users": {},
        },
    }), encoding="utf-8")
    return p


def _make_proc(policy_path: str) -> TelegramCommandProcessor:
    api = MagicMock()
    api.send_message = MagicMock()
    return TelegramCommandProcessor(policy_path=policy_path, api_client=api)


def _send(proc: TelegramCommandProcessor, text: str, *,
          chat_id: str = "100", user_id: str = "1") -> str:
    return proc.handle_text(chat_id=chat_id, user_id=user_id, text=text)


# ---------------------------------------------------------------------------
# NoteEditAction unit tests
# ---------------------------------------------------------------------------

class TestNoteEditAction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))
        self.note = _write_note(self.vault / "10_Proyectos" / "demo.md")
        self.policy_path = str(_make_policy(Path(self.tmp.name), vault_root=str(self.vault)))
        self.action = NoteEditAction(PolicyStore(self.policy_path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_adds_text(self):
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "mode": "append",
            "content": "Nueva sección añadida.",
        })
        self.assertTrue(result.ok)
        content = self.note.read_text(encoding="utf-8")
        self.assertIn("Nueva sección añadida.", content)
        self.assertIn("Body.", content)  # original still present

    def test_replace_overwrites_content(self):
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "mode": "replace",
            "content": "Contenido completamente nuevo.",
        })
        self.assertTrue(result.ok)
        content = self.note.read_text(encoding="utf-8")
        self.assertIn("Contenido completamente nuevo.", content)
        self.assertNotIn("Body.", content)

    def test_result_contains_expected_keys(self):
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "mode": "append",
            "content": "Test.",
        })
        self.assertIn("note_name", result.result)
        self.assertIn("rel_path", result.result)
        self.assertIn("mode", result.result)
        self.assertIn("bytes_written", result.result)

    def test_invalid_mode_raises(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "10_Proyectos/demo.md",
                "mode": "delete",
                "content": "oops",
            })
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_traversal_blocked(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "../etc/passwd",
                "mode": "append",
                "content": "hack",
            })
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_agent_folder_blocked(self):
        agent_note = _write_note(self.vault / "Agent" / "Inbox_Agent" / "some.md")
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "Agent/Inbox_Agent/some.md",
                "mode": "append",
                "content": "blocked",
            })
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_missing_note_returns_not_found(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "10_Proyectos/ghost.md",
                "mode": "append",
                "content": "nothing",
            })
        self.assertEqual(ctx.exception.code, "not_found")


# ---------------------------------------------------------------------------
# NoteMoveFolderAction unit tests
# ---------------------------------------------------------------------------

class TestNoteMoveFolderAction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))
        self.note = _write_note(self.vault / "10_Proyectos" / "demo.md")
        self.policy_path = str(_make_policy(Path(self.tmp.name), vault_root=str(self.vault)))
        self.action = NoteMoveFolderAction(PolicyStore(self.policy_path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_moves_note_to_dest_folder(self):
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "dest_folder": "20_Areas",
        })
        self.assertTrue(result.ok)
        self.assertFalse((self.vault / "10_Proyectos" / "demo.md").exists())
        self.assertTrue((self.vault / "20_Areas" / "demo.md").exists())

    def test_result_contains_expected_keys(self):
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "dest_folder": "20_Areas",
        })
        self.assertIn("note_name", result.result)
        self.assertIn("from_path", result.result)
        self.assertIn("to_path", result.result)
        self.assertIn("dest_folder", result.result)

    def test_dest_agent_folder_blocked(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "10_Proyectos/demo.md",
                "dest_folder": "Agent/Inbox_Agent",
            })
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_dest_not_found_raises(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "10_Proyectos/demo.md",
                "dest_folder": "99_NoExiste",
            })
        self.assertEqual(ctx.exception.code, "not_found")

    def test_traversal_blocked(self):
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            self.action.execute({
                "note_path": "../etc/passwd",
                "dest_folder": "20_Areas",
            })
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_collision_handled_with_suffix(self):
        # Create same note in dest to force collision
        _write_note(self.vault / "20_Areas" / "demo.md")
        result = self.action.execute({
            "note_path": "10_Proyectos/demo.md",
            "dest_folder": "20_Areas",
        })
        self.assertTrue(result.ok)
        # Both files exist in dest (original + moved with timestamp suffix)
        dest_files = list((self.vault / "20_Areas").glob("demo*.md"))
        self.assertEqual(len(dest_files), 2)


# ---------------------------------------------------------------------------
# Conversational intent matching
# ---------------------------------------------------------------------------

class TestE5E6IntentMatching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_path = str(_make_policy(Path(self.tmp.name)))
        self.proc = _make_proc(self.policy_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_aniade_a_intent(self):
        intent = self.proc._match_obsidian_intent(
            normalized="añade a mi nota: nuevo texto aqui",
            original_text="añade a mi nota: nuevo texto aqui",
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.edit_note")
        self.assertEqual(intent["params"]["mode"], "append")
        self.assertEqual(intent["params"]["note_ref"], "mi nota")

    def test_edita_intent(self):
        intent = self.proc._match_obsidian_intent(
            normalized="edita mi nota: contenido nuevo",
            original_text="edita mi nota: contenido nuevo",
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.edit_note")
        self.assertEqual(intent["params"]["mode"], "replace")

    def test_mueve_a_intent(self):
        intent = self.proc._match_obsidian_intent(
            normalized="mueve mi nota a 20_Areas",
            original_text="mueve mi nota a 20_Areas",
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.move_note")
        self.assertEqual(intent["params"]["note_ref"], "mi nota")

    def test_mueve_a_la_carpeta_intent(self):
        intent = self.proc._match_obsidian_intent(
            normalized="mueve demo a la carpeta Proyectos",
            original_text="mueve demo a la carpeta Proyectos",
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent"], "obsidian.move_note")
        self.assertEqual(intent["params"]["dest_folder"], "Proyectos")

    def test_edit_no_content_returns_none(self):
        intent = self.proc._match_obsidian_intent(
            normalized="añade a mi nota",
            original_text="añade a mi nota",
        )
        # No colon separator → no match for edit, may match something else or None
        self.assertIsNone(intent) if intent is None else self.assertNotEqual(intent.get("intent"), "obsidian.edit_note")


# ---------------------------------------------------------------------------
# Confirmation flow for edit and move
# ---------------------------------------------------------------------------

class TestE5E6ConfirmationFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.tmp.name))
        self.note = _write_note(self.vault / "10_Proyectos" / "demo.md")
        self.policy_path = str(_make_policy(Path(self.tmp.name), vault_root=str(self.vault)))
        self.proc = _make_proc(self.policy_path)
        self.proc.session_store.wake(chat_id="100", user_id="1", operator_id="test-operator")

    def tearDown(self):
        self.tmp.cleanup()

    def test_edit_append_confirmation_flow(self):
        reply = _send(self.proc, "añade a demo.md: este texto nuevo")
        self.assertIn("si", reply.lower())  # confirmation prompt
        reply2 = _send(self.proc, "si")
        self.assertIn("Texto añadido", reply2)
        content = self.note.read_text(encoding="utf-8")
        self.assertIn("este texto nuevo", content)

    def test_move_confirmation_flow(self):
        reply = _send(self.proc, "mueve demo.md a 20_Areas")
        self.assertIn("si", reply.lower())
        reply2 = _send(self.proc, "si")
        self.assertIn("Nota movida", reply2)
        self.assertTrue((self.vault / "20_Areas" / "demo.md").exists())

    def test_edit_cancel_no_change(self):
        original = self.note.read_text(encoding="utf-8")
        _send(self.proc, "añade a demo.md: texto que no debe aparecer")
        _send(self.proc, "no")
        self.assertEqual(self.note.read_text(encoding="utf-8"), original)


# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------

class TestE5E6Renders(unittest.TestCase):
    def test_render_note_edited_append(self):
        text = assistant_responses.render_note_edited("demo.md", "10_Proyectos/demo.md", "append")
        self.assertIn("Texto añadido", text)
        self.assertIn("10_Proyectos/demo.md", text)

    def test_render_note_edited_replace(self):
        text = assistant_responses.render_note_edited("demo.md", "10_Proyectos/demo.md", "replace")
        self.assertIn("reemplazada", text.lower())

    def test_render_note_moved(self):
        text = assistant_responses.render_note_moved(
            "demo.md", "10_Proyectos/demo.md", "20_Areas/demo.md"
        )
        self.assertIn("Nota movida", text)
        self.assertIn("10_Proyectos/demo.md", text)
        self.assertIn("20_Areas/demo.md", text)
