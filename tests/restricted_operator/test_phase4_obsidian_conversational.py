"""Tests for Phase 4 — Obsidian conversational layer.

Covers:
- obsidian_intent_resolver: resolve_note, get_note_status
- _match_obsidian_intent: intent detection from phrases
- _handle_obsidian_intent: full flow for list, status, capture, promote
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "agents" / "openclaw" / "restricted_operator"
BRIDGE_DIR = ROOT / "scripts" / "agents" / "openclaw"

if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from obsidian_intent_resolver import ResolveResult, get_note_status, resolve_note  # noqa: E402
from policy import PolicyStore  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INBOX_DIR = "Agent/Inbox_Agent"


def _note_content(
    *,
    run_id: str = "test-001",
    title: str = "Test Note",
    status: str = "pending_triage",
) -> str:
    return (
        "---\n"
        f'run_id: "{run_id}"\n'
        f'capture_status: "{status}"\n'
        'created_at_utc: "2026-04-14T10:00:00Z"\n'
        "---\n\n"
        f"# {title}\n\n"
        "## Captura\n\nBody text.\n"
    )


def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / INBOX_DIR).mkdir(parents=True)
    return vault


def _write_note(inbox: Path, *, name: str, run_id: str = "r1", status: str = "pending_triage") -> Path:
    path = inbox / name
    path.write_text(_note_content(run_id=run_id, status=status), encoding="utf-8")
    return path


def _make_policy(root: Path, *, vault_root: str = "", enabled: bool = True) -> Path:
    policy = {
        "broker": {
            "bind_host": "127.0.0.1",
            "bind_port": 18899,
            "audit_log_path": str(root / "audit.jsonl"),
            "state_store_path": str(root / "state.json"),
            "dropzone_dir": str(root / "dropzone"),
            "max_tail_lines": 20,
            "max_write_bytes": 4096,
        },
        "vault_inbox": {"vault_root": vault_root},
        "actions": {
            "action.inbox.write.v1": {
                "enabled": enabled, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "test",
            },
            "action.draft.promote.v1": {
                "enabled": enabled, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "test",
            },
            "action.report.promote.v1": {
                "enabled": enabled, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "test",
            },
        },
        "operator_auth": {
            "roles": {
                "viewer": ["policy.read", "operator.read"],
                "operator": ["policy.read", "policy.mutate", "operator.read",
                             "operator.trigger", "operator.write"],
            },
            "operators": {
                "op1": {"role": "operator", "enabled": True, "display_name": "Op1", "reason": "test"},
                "viewer1": {"role": "viewer", "enabled": True, "display_name": "V1", "reason": "test"},
            },
        },
        "telegram": {
            "enabled": True,
            "bot_token_env": "OPENCLAW_TELEGRAM_BOT_TOKEN",
            "api_base_url": "https://api.telegram.org",
            "poll_timeout_seconds": 1,
            "audit_tail_lines": 5,
            "offset_store_path": str(root / "offset.json"),
            "runtime_status_path": str(root / "runtime_status.json"),
            "rate_limit_window_seconds": 30,
            "rate_limit_max_requests": 20,
            "max_command_length": 512,
            "allowed_chats": {
                "1001": {"operator_id": "op1", "enabled": True, "display_name": "Op Chat", "reason": "test"},
                "2002": {"operator_id": "viewer1", "enabled": True, "display_name": "Viewer", "reason": "test"},
            },
            "allowed_users": {},
        },
    }
    path = root / "policy.json"
    path.write_text(json.dumps(policy))
    return path


class _FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, *, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


# ---------------------------------------------------------------------------
# obsidian_intent_resolver tests
# ---------------------------------------------------------------------------

class TestResolveNote(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.vault = _make_vault(Path(self.td.name))
        self.inbox = self.vault / INBOX_DIR

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_returns_none_for_empty_inbox(self) -> None:
        self.assertIsNone(resolve_note(str(self.vault), "ultima"))

    def test_resolve_ultima(self) -> None:
        _write_note(self.inbox, name="20260414T090000Z_inbox_a.md", run_id="a")
        _write_note(self.inbox, name="20260414T100000Z_inbox_b.md", run_id="b")
        r = resolve_note(str(self.vault), "ultima")
        assert r is not None
        self.assertEqual(r.run_id, "b")  # newest by name

    def test_resolve_last(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_z.md", run_id="z")
        r = resolve_note(str(self.vault), "last")
        assert r is not None
        self.assertEqual(r.run_id, "z")

    def test_resolve_exact_filename(self) -> None:
        name = "20260414T100000Z_inbox_exact.md"
        _write_note(self.inbox, name=name, run_id="exact")
        r = resolve_note(str(self.vault), name)
        assert r is not None
        self.assertEqual(r.note_name, name)
        self.assertEqual(r.capture_status, "pending_triage")

    def test_resolve_exact_filename_not_found(self) -> None:
        # Inbox is empty → _inbox_notes_newest_first returns [] → resolve_note returns None
        r = resolve_note(str(self.vault), "20260414T100000Z_inbox_missing.md")
        self.assertIsNone(r)

    def test_resolve_exact_filename_not_found_with_other_notes(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_other.md", run_id="other")
        r = resolve_note(str(self.vault), "20260414T100000Z_inbox_missing.md")
        assert r is not None
        self.assertEqual(r.capture_status, "not_found")

    def test_resolve_run_id_token(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_myrun.md", run_id="myrun")
        r = resolve_note(str(self.vault), "myrun")
        assert r is not None
        self.assertEqual(r.run_id, "myrun")

    def test_resolve_ambiguous(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_abc1.md", run_id="abc1")
        _write_note(self.inbox, name="20260414T110000Z_inbox_abc2.md", run_id="abc2")
        r = resolve_note(str(self.vault), "abc")
        assert r is not None
        self.assertTrue(r.ambiguous)
        self.assertIn("20260414T100000Z_inbox_abc1.md", r.candidates)

    def test_get_note_status_found(self) -> None:
        name = "20260414T100000Z_inbox_s.md"
        _write_note(self.inbox, name=name, run_id="s", status="promoted_to_draft")
        info = get_note_status(str(self.vault), name)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info["capture_status"], "promoted_to_draft")

    def test_get_note_status_not_found(self) -> None:
        info = get_note_status(str(self.vault), "20260414T100000Z_inbox_missing.md")
        self.assertIsNone(info)


# ---------------------------------------------------------------------------
# _match_obsidian_intent detection tests
# ---------------------------------------------------------------------------

class TestObsidianIntentDetection(unittest.TestCase):
    """Test that phrases are correctly mapped to obsidian intents."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.policy_path = _make_policy(self.root)
        self.proc = TelegramCommandProcessor(str(self.policy_path), api_client=_FakeClient())

    def tearDown(self) -> None:
        self.td.cleanup()

    def _intent(self, text: str) -> dict | None:
        return self.proc._detect_conversational_intent(text, assistant_awake=False)

    def test_list_pending_phrase(self) -> None:
        r = self._intent("qué tengo pendiente")
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.list_pending")

    def test_list_pending_phrase2(self) -> None:
        r = self._intent("notas pendientes")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.list_pending")

    def test_list_report_ready_phrase(self) -> None:
        r = self._intent("listas para report")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.list_report_ready")

    def test_list_report_ready_phrase2(self) -> None:
        r = self._intent("notas en draft")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.list_report_ready")

    def test_show_status_phrase(self) -> None:
        r = self._intent("estado de tg-001")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.show_note_status")
        # "-" is punctuation → stripped to space by _normalize_text; ref is "tg 001"
        self.assertIn("tg", r["params"]["note_ref"])

    def test_show_status_phrase2(self) -> None:
        r = self._intent("qué estado tiene myrun")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.show_note_status")
        self.assertIn("myrun", r["params"]["note_ref"])

    def test_promote_to_draft_ultima(self) -> None:
        r = self._intent("promueve la ultima a draft")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.promote_to_draft")
        self.assertEqual(r["params"]["note_ref"], "ultima")

    def test_promote_to_draft_run_id(self) -> None:
        r = self._intent("promueve tg-001 a draft")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.promote_to_draft")
        # "-" stripped to space by normalization; resolver handles via alphanumeric match
        self.assertIn("tg", r["params"]["note_ref"])

    def test_promote_to_report_ultima(self) -> None:
        r = self._intent("promueve la ultima a report")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.promote_to_report")
        self.assertEqual(r["params"]["note_ref"], "ultima")

    def test_promote_to_report_run_id(self) -> None:
        r = self._intent("promueve tg-002 a report")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.promote_to_report")
        self.assertIn("tg", r["params"]["note_ref"])

    def test_capture_with_separator(self) -> None:
        r = self._intent("guarda esta idea: Mi plan :: Revisar los costes")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.capture")
        self.assertEqual(r["params"]["title"], "Mi plan")
        self.assertIn("Revisar", r["params"]["body"])

    def test_capture_anota_esto(self) -> None:
        r = self._intent("anota esto: Reunión :: Hemos acordado subir el precio")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.capture")
        self.assertEqual(r["params"]["title"], "Reunión")

    def test_capture_without_separator_returns_clarify(self) -> None:
        r = self._intent("guarda esta idea: solo un titulo sin cuerpo")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.capture_clarify")

    def test_capture_keyword_alone_returns_clarify(self) -> None:
        r = self._intent("guarda una nota")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.capture_clarify")

    def test_unrelated_phrase_returns_none(self) -> None:
        r = self._intent("qué tiempo hace hoy")
        self.assertIsNone(r)

    def test_existing_commands_not_captured(self) -> None:
        r = self._intent("estado")
        assert r is not None
        self.assertEqual(r["intent"], "status")  # existing intent, not obsidian

    def test_promote_draft_not_confused_with_report(self) -> None:
        r = self._intent("promueve la ultima a draft")
        assert r is not None
        self.assertEqual(r["intent"], "obsidian.promote_to_draft")
        self.assertNotEqual(r["intent"], "obsidian.promote_to_report")


# ---------------------------------------------------------------------------
# Full conversational flow tests
# ---------------------------------------------------------------------------

class TestObsidianConversationalFlow(unittest.TestCase):

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = _make_vault(self.root)
        self.inbox = self.vault / INBOX_DIR
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault), enabled=True)
        self.proc = TelegramCommandProcessor(str(self.policy_path), api_client=_FakeClient())

    def tearDown(self) -> None:
        self.td.cleanup()

    # --- list ---

    def test_list_pending_empty(self) -> None:
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="qué tengo pendiente")
        self.assertIn("pending_triage", reply.lower())

    def test_list_pending_shows_notes(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_a.md", run_id="a")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="notas pendientes")
        self.assertIn("20260414T100000Z_inbox_a.md", reply)

    def test_list_report_ready_empty(self) -> None:
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="listas para report")
        self.assertIn("promoted_to_draft", reply.lower())

    def test_list_report_ready_shows_notes(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_b.md", run_id="b", status="promoted_to_draft")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="notas en draft")
        self.assertIn("20260414T100000Z_inbox_b.md", reply)

    def test_list_viewer_allowed(self) -> None:
        reply = self.proc.handle_text(chat_id="2002", user_id="", text="notas pendientes")
        # viewer has operator.read — should succeed (even if empty)
        self.assertNotIn("no autorizado", reply.lower())

    # --- show status ---

    def test_show_status_found(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_myrun.md", run_id="myrun")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="estado de myrun")
        self.assertIn("pending_triage", reply)
        self.assertIn("myrun", reply)

    def test_show_status_not_found(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_other.md", run_id="other")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="estado de noinexiste")
        self.assertIn("no", reply.lower())

    def test_show_status_ambiguous(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_abc1.md", run_id="abc1")
        _write_note(self.inbox, name="20260414T110000Z_inbox_abc2.md", run_id="abc2")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="estado de abc")
        self.assertIn("abc", reply.lower())

    # --- capture ---

    def test_capture_clarify_no_separator(self) -> None:
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="guarda esta idea: solo titulo")
        self.assertIn("::", reply)  # clarification shows "::"

    def test_capture_with_separator_requests_confirmation(self) -> None:
        reply = self.proc.handle_text(
            chat_id="1001", user_id="",
            text="guarda esta idea: Mi plan :: Revisar costes del proyecto",
        )
        self.assertIn("inbox.write", reply)
        self.assertIn("Mi plan", reply)

    def test_capture_confirmation_and_accept(self) -> None:
        self.proc.handle_text(
            chat_id="1001", user_id="",
            text="guarda esta idea: Mi plan :: Revisar costes del proyecto",
        )
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="si")
        self.assertIn("guardada", reply.lower())

    def test_capture_confirmation_reject(self) -> None:
        self.proc.handle_text(
            chat_id="1001", user_id="",
            text="guarda esta idea: Mi plan :: Revisar costes",
        )
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="no")
        self.assertIn("cancelada", reply.lower())
        # Inbox is empty — no note written
        self.assertEqual(list(self.inbox.iterdir()), [])

    def test_capture_viewer_unauthorized(self) -> None:
        reply = self.proc.handle_text(
            chat_id="2002", user_id="",
            text="guarda esta idea: Prueba :: Cuerpo de prueba",
        )
        self.assertIn("no autorizado", reply.lower())

    def test_capture_action_disabled_blocks(self) -> None:
        td2 = tempfile.TemporaryDirectory()
        try:
            root2 = Path(td2.name)
            vault2 = _make_vault(root2)
            p2 = _make_policy(root2, vault_root=str(vault2), enabled=False)
            proc2 = TelegramCommandProcessor(str(p2), api_client=_FakeClient())
            reply = proc2.handle_text(
                chat_id="1001", user_id="",
                text="guarda esta idea: Titulo :: Cuerpo",
            )
            self.assertIn("disabled", reply.lower())
        finally:
            td2.cleanup()

    # --- promote to draft ---

    def test_promote_to_draft_ultima_confirms(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_p.md", run_id="p")
        reply = self.proc.handle_text(
            chat_id="1001", user_id="", text="promueve la ultima a draft"
        )
        self.assertIn("draft.promote", reply)
        self.assertIn("20260414T100000Z_inbox_p.md", reply)

    def test_promote_to_draft_accept(self) -> None:
        name = "20260414T100000Z_inbox_p.md"
        _write_note(self.inbox, name=name, run_id="p")
        self.proc.handle_text(chat_id="1001", user_id="", text="promueve la ultima a draft")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="si")
        self.assertIn("draft", reply.lower())
        # STAGED_INPUT.md created
        self.assertTrue((self.inbox / "STAGED_INPUT.md").exists())

    def test_promote_to_draft_reject(self) -> None:
        name = "20260414T100000Z_inbox_p.md"
        _write_note(self.inbox, name=name, run_id="p")
        self.proc.handle_text(chat_id="1001", user_id="", text="promueve la ultima a draft")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="no")
        self.assertIn("cancelada", reply.lower())
        self.assertFalse((self.inbox / "STAGED_INPUT.md").exists())

    def test_promote_to_draft_empty_inbox(self) -> None:
        reply = self.proc.handle_text(
            chat_id="1001", user_id="", text="promueve la ultima a draft"
        )
        self.assertIn("no hay", reply.lower())

    def test_promote_to_draft_ambiguous(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_abc1.md", run_id="abc1")
        _write_note(self.inbox, name="20260414T110000Z_inbox_abc2.md", run_id="abc2")
        reply = self.proc.handle_text(
            chat_id="1001", user_id="", text="promueve abc a draft"
        )
        self.assertIn("abc", reply.lower())

    def test_promote_to_draft_viewer_unauthorized(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_p.md", run_id="p")
        reply = self.proc.handle_text(
            chat_id="2002", user_id="", text="promueve la ultima a draft"
        )
        self.assertIn("no autorizado", reply.lower())

    # --- promote to report ---

    def test_promote_to_report_ultima_confirms(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_r.md", run_id="r", status="promoted_to_draft")
        reply = self.proc.handle_text(
            chat_id="1001", user_id="", text="promueve la ultima a report"
        )
        self.assertIn("report.promote", reply)

    def test_promote_to_report_accept(self) -> None:
        name = "20260414T100000Z_inbox_r.md"
        _write_note(self.inbox, name=name, run_id="r", status="promoted_to_draft")
        self.proc.handle_text(chat_id="1001", user_id="", text="promueve la ultima a report")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="si")
        self.assertIn("report", reply.lower())
        self.assertTrue((self.inbox / "REPORT_INPUT.md").exists())

    def test_promote_to_report_wrong_status_fails(self) -> None:
        name = "20260414T100000Z_inbox_r.md"
        _write_note(self.inbox, name=name, run_id="r", status="pending_triage")
        self.proc.handle_text(chat_id="1001", user_id="", text="promueve la ultima a report")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="si")
        # Broker rejects because status is pending_triage, not promoted_to_draft
        # Phase 6: error message is conversational ("No puedo promover…")
        self.assertIn("promoted_to_draft", reply.lower())

    # --- slash commands still work ---

    def test_slash_commands_unaffected(self) -> None:
        _write_note(self.inbox, name="20260414T100000Z_inbox_q.md", run_id="q")
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="/draft_promote")
        self.assertIn("20260414T100000Z_inbox_q.md", reply)


if __name__ == "__main__":
    unittest.main()
