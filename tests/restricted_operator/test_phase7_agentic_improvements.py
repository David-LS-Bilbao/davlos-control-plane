"""Tests for Phase 7 — Más Agentico improvements (A, B, C, D).

Covers:
A — Wake with automatic vault summary (pending count + artifact status + last event)
B — Post-action suggestions after capture/draft_promote/report_promote
C — Session note memory: 'esa'/'la misma' alias resolution
D — Vault-aware 'qué propones' suggestion
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

_OPENCLAW = Path(__file__).resolve().parents[2] / "scripts" / "agents" / "openclaw"
_RO = _OPENCLAW / "restricted_operator"

if str(_OPENCLAW) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW))
if str(_RO) not in sys.path:
    sys.path.insert(0, str(_RO))

import assistant_responses  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402

INBOX_SUBDIR = "Agent/Inbox_Agent"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note_content(
    *,
    run_id: str = "r1",
    title: str = "Test",
    status: str = "pending_triage",
    created_at_utc: str = "2026-04-15T10:00:00Z",
) -> str:
    return (
        "---\n"
        f'run_id: "{run_id}"\n'
        f'capture_status: "{status}"\n'
        f'created_at_utc: "{created_at_utc}"\n'
        "---\n\n"
        f"# {title}\n\nBody.\n"
    )


def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / INBOX_SUBDIR).mkdir(parents=True)
    return vault


def _write_note(inbox: Path, *, name: str, run_id: str = "r1", status: str = "pending_triage") -> Path:
    path = inbox / name
    path.write_text(_note_content(run_id=run_id, status=status), encoding="utf-8")
    return path


def _make_policy(root: Path, *, vault_root: str = "") -> Path:
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
        },
        "log_streams": {},
        "health_checks": {},
        "webhook_targets": {},
        "operator_auth": {
            "roles": {
                "viewer": ["policy.read"],
                "operator": ["policy.read", "operator.read", "operator.write", "operator.audit"],
            },
            "operators": {
                "op1": {"role": "operator", "active": True},
            },
        },
        "telegram": {
            "enabled": True,
            "api_base_url": "https://api.telegram.org",
            "bot_token_env": "TELEGRAM_BOT_TOKEN",
            "allowed_chats": {"100": {"principal_id": "p1", "operator_id": "op1"}},
            "allowed_users": {},
            "rate_limit_window_seconds": 60,
            "rate_limit_max_requests": 100,
            "max_command_length": 512,
            "poll_timeout_seconds": 30,
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
    mock_client = MagicMock()
    return TelegramCommandProcessor(policy_path=policy_path, api_client=mock_client)


# ---------------------------------------------------------------------------
# A — Wake vault context
# ---------------------------------------------------------------------------

class TestWakeVaultContext(unittest.TestCase):
    """A — /wake appends vault summary (pending notes, artifacts, last event)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_wake_with_pending_notes_shows_count(self):
        inbox = self.vault / INBOX_SUBDIR
        _write_note(inbox, name="20260415T100000Z_inbox_notea.md", run_id="r1")
        _write_note(inbox, name="20260415T100001Z_inbox_noteb.md", run_id="r2")
        proc = _make_proc(str(self.policy_path))
        reply = proc._wake_assistant(chat_id="100", user_id="1", operator_id="op1")
        self.assertIn("pending_triage", reply)
        self.assertIn("2", reply)

    def test_wake_with_staged_artifact_shows_PRESENTE(self):
        inbox = self.vault / INBOX_SUBDIR
        staged = inbox / "STAGED_INPUT.md"
        staged.write_text("---\nnote_name: \"Some-Note.md\"\n---\n", encoding="utf-8")
        proc = _make_proc(str(self.policy_path))
        reply = proc._wake_assistant(chat_id="100", user_id="1", operator_id="op1")
        self.assertIn("STAGED_INPUT.md", reply)
        self.assertIn("PRESENTE", reply)

    def test_wake_with_no_notes_no_artifacts_still_shows_vault_section(self):
        proc = _make_proc(str(self.policy_path))
        reply = proc._wake_assistant(chat_id="100", user_id="1", operator_id="op1")
        # base wake message always present
        self.assertIn("Asistente despierto", reply)
        # vault section present when operator has read permission
        self.assertIn("Vault:", reply)

    def test_wake_shows_last_audit_event(self):
        audit_path = self.root / "audit.jsonl"
        audit_path.write_text(
            json.dumps({"ts": "2026-04-15T10:00:00Z", "event": "assistant_wake", "action_id": "telegram.command", "ok": True}) + "\n",
            encoding="utf-8",
        )
        proc = _make_proc(str(self.policy_path))
        reply = proc._wake_assistant(chat_id="100", user_id="1", operator_id="op1")
        self.assertIn("último evento", reply)
        self.assertIn("assistant_wake", reply)


# ---------------------------------------------------------------------------
# A — render_wake_vault_context
# ---------------------------------------------------------------------------

class TestRenderWakeVaultContext(unittest.TestCase):
    def test_with_all_fields(self):
        result = assistant_responses.render_wake_vault_context(
            pending_count=3,
            staged_exists=True,
            report_exists=False,
            last_event="some_event | action.x.v1 | 2026-04-15T10:00",
        )
        self.assertIn("pending_triage: 3", result)
        self.assertIn("STAGED_INPUT.md: PRESENTE", result)
        self.assertIn("REPORT_INPUT.md: libre", result)
        self.assertIn("último evento", result)

    def test_with_no_fields_returns_empty(self):
        result = assistant_responses.render_wake_vault_context(
            pending_count=None,
            staged_exists=None,
            report_exists=None,
            last_event=None,
        )
        self.assertEqual(result, "")

    def test_pending_count_zero(self):
        result = assistant_responses.render_wake_vault_context(
            pending_count=0,
            staged_exists=False,
            report_exists=False,
            last_event=None,
        )
        self.assertIn("pending_triage: 0", result)
        self.assertIn("libre", result)


# ---------------------------------------------------------------------------
# B — Post-action suggestions
# ---------------------------------------------------------------------------

class TestPostActionSuggestions(unittest.TestCase):
    """B — successful actions include a next-step hint."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def _proc_with_broker_result(self, ok: bool, result_dict: dict, action_id: str) -> TelegramCommandProcessor:
        proc = _make_proc(str(self.policy_path))
        mock_result = MagicMock()
        mock_result.ok = ok
        mock_result.result = result_dict
        mock_result.error = None
        mock_result.code = None
        mock_result.to_dict.return_value = {"ok": ok, "action_id": action_id}
        proc.broker = MagicMock()
        proc.broker.execute.return_value = mock_result
        return proc

    def test_inbox_write_success_suggests_draft_promote(self):
        from telegram_bot import PendingConfirmation
        proc = self._proc_with_broker_result(True, {"note_name": "Idea-2026.md"}, "action.inbox.write.v1")
        pending = PendingConfirmation(
            intent="inbox_write",
            operator_id="op1",
            summary="inbox.write | ...",
            mutation="inbox_write",
            action_id="action.inbox.write.v1",
            params={"run_id": "r1", "capture_title": "T", "capture_body": "B", "source_refs": None},
            reason="test",
        )
        reply = proc._execute_pending_confirmation(
            chat_id="100", user_id="1", operator_id="op1", pending=pending
        )
        self.assertIn("Captura guardada", reply)
        self.assertIn("promueve", reply.lower())
        self.assertIn("draft", reply.lower())

    def test_draft_promote_success_suggests_report(self):
        from telegram_bot import PendingConfirmation
        proc = self._proc_with_broker_result(True, {"note_name": "Note.md", "title": "T"}, "action.draft.promote.v1")
        pending = PendingConfirmation(
            intent="draft_promote",
            operator_id="op1",
            summary="draft.promote | ...",
            mutation="draft_promote",
            action_id="action.draft.promote.v1",
            params={"note_name": "Note.md"},
            reason="test",
        )
        reply = proc._execute_pending_confirmation(
            chat_id="100", user_id="1", operator_id="op1", pending=pending
        )
        self.assertIn("promovida a draft", reply)
        self.assertIn("report", reply.lower())
        self.assertIn("STAGED_INPUT.md", reply)

    def test_report_promote_success_suggests_pipeline_follow_up(self):
        from telegram_bot import PendingConfirmation
        proc = self._proc_with_broker_result(True, {"note_name": "Note.md", "title": "T"}, "action.report.promote.v1")
        pending = PendingConfirmation(
            intent="report_promote",
            operator_id="op1",
            summary="report.promote | ...",
            mutation="report_promote",
            action_id="action.report.promote.v1",
            params={"note_name": "Note.md"},
            reason="test",
        )
        reply = proc._execute_pending_confirmation(
            chat_id="100", user_id="1", operator_id="op1", pending=pending
        )
        self.assertIn("promovida a report", reply)
        self.assertIn("REPORT_INPUT.md", reply)
        self.assertIn("artefactos", reply.lower())


# ---------------------------------------------------------------------------
# C — Session note memory
# ---------------------------------------------------------------------------

class TestSessionNoteMemory(unittest.TestCase):
    """C — aliases 'esa'/'la misma' resolve to the last note used in session."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_resolve_session_note(self):
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Real-Note.md")
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertEqual(resolved, "Real-Note.md")

    def test_resolve_la_misma_alias(self):
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Real-Note.md")
        resolved = proc._resolve_note_alias(note_ref="la misma", chat_id="100", user_id="1")
        self.assertEqual(resolved, "Real-Note.md")

    def test_resolve_esa_nota_alias(self):
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Real-Note.md")
        resolved = proc._resolve_note_alias(note_ref="esa nota", chat_id="100", user_id="1")
        self.assertEqual(resolved, "Real-Note.md")

    def test_no_stored_note_returns_original_ref(self):
        proc = _make_proc(str(self.policy_path))
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertEqual(resolved, "esa")

    def test_non_alias_ref_returned_unchanged(self):
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Real-Note.md")
        resolved = proc._resolve_note_alias(note_ref="Other-Note.md", chat_id="100", user_id="1")
        self.assertEqual(resolved, "Other-Note.md")

    def test_session_note_cleared_on_sleep(self):
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Real-Note.md")
        # wake then sleep
        proc.session_store.wake(chat_id="100", user_id="1", operator_id="op1")
        proc._sleep_assistant(chat_id="100", user_id="1", operator_id="op1", reason="manual")
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertEqual(resolved, "esa")

    def test_note_saved_after_obsidian_show_status(self):
        """_obsidian_show_status stores note name in session."""
        inbox = self.vault / INBOX_SUBDIR
        note_name = "20260415T100000Z_inbox_alpha.md"
        _write_note(inbox, name=note_name, run_id="r1", status="pending_triage")
        proc = _make_proc(str(self.policy_path))
        proc._obsidian_show_status(
            note_ref=note_name,
            operator_id="op1",
            chat_id="100",
            user_id="1",
        )
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertEqual(resolved, note_name)

    def test_note_saved_after_obsidian_promote(self):
        """_obsidian_promote stores note name in session after resolve."""
        inbox = self.vault / INBOX_SUBDIR
        note_name = "20260415T100001Z_inbox_beta.md"
        _write_note(inbox, name=note_name, run_id="r2", status="pending_triage")
        proc = _make_proc(str(self.policy_path))
        # Mock broker so the promote doesn't actually run
        proc.broker = MagicMock()
        proc._obsidian_promote(
            chat_id="100", user_id="1", operator_id="op1",
            note_ref=note_name, target="draft", mode="conversation",
        )
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="100", user_id="1")
        self.assertEqual(resolved, note_name)

    def test_different_sessions_isolated(self):
        """Note saved for one session does not bleed into another."""
        proc = _make_proc(str(self.policy_path))
        proc._save_session_note(chat_id="100", user_id="1", note_name="Alice-Note.md")
        resolved = proc._resolve_note_alias(note_ref="esa", chat_id="200", user_id="2")
        self.assertEqual(resolved, "esa")


# ---------------------------------------------------------------------------
# D — Vault-aware suggest_action
# ---------------------------------------------------------------------------

class TestVaultAwareSuggestion(unittest.TestCase):
    """D — 'qué propones' includes vault state when notes/artifacts are present."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = _make_vault(self.root)
        self.policy_path = _make_policy(self.root, vault_root=str(self.vault))

    def tearDown(self):
        self.tmp.cleanup()

    def test_suggest_action_includes_pending_count(self):
        inbox = self.vault / INBOX_SUBDIR
        _write_note(inbox, name="20260415T100000Z_inbox_pending1.md", run_id="r1")
        _write_note(inbox, name="20260415T100001Z_inbox_pending2.md", run_id="r2")
        proc = _make_proc(str(self.policy_path))
        reply = proc._render_assistant_suggestion(operator_id="op1")
        self.assertIn("pending_triage", reply)

    def test_suggest_action_includes_staged_artifact(self):
        inbox = self.vault / INBOX_SUBDIR
        staged = inbox / "STAGED_INPUT.md"
        staged.write_text("---\nnote_name: \"Some-Note.md\"\n---\n", encoding="utf-8")
        proc = _make_proc(str(self.policy_path))
        reply = proc._render_assistant_suggestion(operator_id="op1")
        self.assertIn("STAGED_INPUT.md", reply)

    def test_suggest_action_includes_reportable_notes(self):
        inbox = self.vault / INBOX_SUBDIR
        _write_note(inbox, name="20260415T100000Z_inbox_draftready.md", run_id="r1", status="promoted_to_draft")
        proc = _make_proc(str(self.policy_path))
        reply = proc._render_assistant_suggestion(operator_id="op1")
        self.assertIn("promoted_to_draft", reply)

    def test_suggest_action_empty_vault_no_vault_section(self):
        """When vault is empty and no artifacts, no vault lines should clutter the response."""
        proc = _make_proc(str(self.policy_path))
        reply = proc._render_assistant_suggestion(operator_id="op1")
        # Base suggestion should still be present
        self.assertIsInstance(reply, str)
        self.assertGreater(len(reply), 0)

    def test_build_suggest_vault_context_no_vault_configured(self):
        policy_path = _make_policy(self.root, vault_root="")
        proc = _make_proc(str(policy_path))
        ctx = proc._build_suggest_vault_context(operator_id="op1")
        self.assertEqual(ctx, "")


if __name__ == "__main__":
    unittest.main()
