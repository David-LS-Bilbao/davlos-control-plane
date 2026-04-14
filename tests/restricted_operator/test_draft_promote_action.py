from __future__ import annotations

import json
import os
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

from actions import DraftPromoteAction  # noqa: E402
from broker import RestrictedOperatorBroker  # noqa: E402
from models import BrokerRequest  # noqa: E402
from policy import PolicyStore  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402
from vault_draft_promote_bridge import (  # noqa: E402
    VaultDraftPromoteBridgeError,
    invoke_draft_promote,
    list_promotable_notes,
)


# ---------------------------------------------------------------------------
# Helper: minimal inbox note content (mirrors openclaw_vault_inbox_writer output)
# ---------------------------------------------------------------------------
def _inbox_note_content(
    *,
    run_id: str = "test-001",
    title: str = "Test Title",
    body: str = "Body text for testing.",
    status: str = "pending_triage",
) -> str:
    return (
        "---\n"
        'managed_by: obsi-claw-AI_agent\n'
        'agent_zone: Agent/Inbox_Agent\n'
        f'run_id: "{run_id}"\n'
        f'created_at_utc: "2026-04-13T10:00:00Z"\n'
        f'updated_at_utc: "2026-04-13T10:00:00Z"\n'
        'source_refs: []\n'
        f'capture_status: "{status}"\n'
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Contexto\n"
        "\n"
        "Captura rapida create-only para triage posterior dentro de Agent/Inbox_Agent.\n"
        "\n"
        "## Entrada\n"
        "\n"
        "- input_request_file: `telegram/inbox_write`\n"
        "\n"
        "## Captura\n"
        "\n"
        f"{body}\n"
        "\n"
        "## Trazabilidad\n"
        "\n"
        f'- operation: `inbox.write`\n'
        f'- run_id: `{run_id}`\n'
        '- created_at_utc: `2026-04-13T10:00:00Z`\n'
        '- source_refs: `[]`\n'
    )


INBOX_NOTE_NAME = "20260413T100000Z_inbox_test-001.md"


def _make_policy(root: Path, *, vault_root: str = "", action_enabled: bool = False) -> Path:
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
        "vault_inbox": {
            "vault_root": vault_root,
        },
        "actions": {
            "action.inbox.write.v1": {
                "enabled": action_enabled,
                "mode": "restricted",
                "expires_at": None,
                "one_shot": False,
                "reason": "test",
                "updated_by": "test",
                "permission": "operator.write",
                "description": "test inbox write",
            },
            "action.draft.promote.v1": {
                "enabled": action_enabled,
                "mode": "restricted",
                "expires_at": None,
                "one_shot": False,
                "reason": "test",
                "updated_by": "test",
                "permission": "operator.write",
                "description": "test draft promote",
            },
        },
        "operator_auth": {
            "roles": {
                "viewer": ["policy.read", "operator.read"],
                "operator": [
                    "policy.read",
                    "policy.mutate",
                    "operator.read",
                    "operator.trigger",
                    "operator.write",
                ],
                "admin": [
                    "policy.read",
                    "policy.mutate",
                    "operator.audit",
                    "operator.read",
                    "operator.trigger",
                    "operator.write",
                    "operator.control",
                ],
            },
            "operators": {
                "op1": {
                    "role": "operator",
                    "enabled": True,
                    "display_name": "Operator 1",
                    "reason": "test",
                },
                "viewer1": {
                    "role": "viewer",
                    "enabled": True,
                    "display_name": "Viewer 1",
                    "reason": "test",
                },
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
                "1001": {
                    "operator_id": "op1",
                    "enabled": True,
                    "display_name": "Operator Chat",
                    "reason": "test",
                },
                "2002": {
                    "operator_id": "viewer1",
                    "enabled": True,
                    "display_name": "Viewer Chat",
                    "reason": "test",
                },
            },
            "allowed_users": {},
        },
    }
    path = root / "policy.json"
    path.write_text(json.dumps(policy))
    return path


class _FakeTelegramClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, *, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


# ---------------------------------------------------------------------------
# Bridge unit tests
# ---------------------------------------------------------------------------
class TestDraftPromoteBridge(unittest.TestCase):
    """Direct bridge-level tests for invoke_draft_promote."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "Agent" / "Inbox_Agent"
        self.inbox.mkdir(parents=True)

    def tearDown(self) -> None:
        self.td.cleanup()

    def _write_inbox_note(self, name: str = INBOX_NOTE_NAME, **kwargs: str) -> Path:
        path = self.inbox / name
        path.write_text(_inbox_note_content(**kwargs), encoding="utf-8")
        return path

    def test_successful_promote(self) -> None:
        self._write_inbox_note()
        result = invoke_draft_promote(vault_root=str(self.vault), note_name=INBOX_NOTE_NAME)
        self.assertEqual(result["note_name"], INBOX_NOTE_NAME)
        self.assertEqual(result["run_id"], "test-001")
        self.assertEqual(result["original_status"], "pending_triage")
        self.assertEqual(result["new_status"], "promoted_to_draft")
        # STAGED_INPUT.md created
        staged = self.inbox / "STAGED_INPUT.md"
        self.assertTrue(staged.exists())
        staged_content = staged.read_text(encoding="utf-8")
        self.assertIn("draft.write", staged_content)
        self.assertIn("test-001", staged_content)
        # Source note updated
        source_content = (self.inbox / INBOX_NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("promoted_to_draft", source_content)
        self.assertNotIn("pending_triage", source_content)

    def test_not_found_raises(self) -> None:
        with self.assertRaises(VaultDraftPromoteBridgeError) as ctx:
            invoke_draft_promote(
                vault_root=str(self.vault),
                note_name="20260413T100000Z_inbox_missing.md",
            )
        self.assertEqual(ctx.exception.code, "not_found")

    def test_already_promoted_raises(self) -> None:
        self._write_inbox_note(status="promoted_to_draft")
        with self.assertRaises(VaultDraftPromoteBridgeError) as ctx:
            invoke_draft_promote(vault_root=str(self.vault), note_name=INBOX_NOTE_NAME)
        self.assertEqual(ctx.exception.code, "not_promotable")

    def test_staging_conflict_raises(self) -> None:
        self._write_inbox_note()
        (self.inbox / "STAGED_INPUT.md").write_text("conflict", encoding="utf-8")
        with self.assertRaises(VaultDraftPromoteBridgeError) as ctx:
            invoke_draft_promote(vault_root=str(self.vault), note_name=INBOX_NOTE_NAME)
        self.assertEqual(ctx.exception.code, "staging_conflict")

    def test_invalid_note_name_pattern_raises(self) -> None:
        with self.assertRaises(VaultDraftPromoteBridgeError) as ctx:
            invoke_draft_promote(vault_root=str(self.vault), note_name="bad_name.md")
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_vault_root_not_configured_raises(self) -> None:
        with self.assertRaises(VaultDraftPromoteBridgeError) as ctx:
            invoke_draft_promote(vault_root="relative/path", note_name=INBOX_NOTE_NAME)
        self.assertEqual(ctx.exception.code, "invalid_config")


# ---------------------------------------------------------------------------
# Bridge: list_promotable_notes
# ---------------------------------------------------------------------------
class TestListPromotableNotes(unittest.TestCase):

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "Agent" / "Inbox_Agent"
        self.inbox.mkdir(parents=True)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_lists_pending_triage_notes(self) -> None:
        (self.inbox / "20260413T100000Z_inbox_a.md").write_text(
            _inbox_note_content(run_id="a"), encoding="utf-8"
        )
        (self.inbox / "20260413T110000Z_inbox_b.md").write_text(
            _inbox_note_content(run_id="b", status="promoted_to_draft"), encoding="utf-8"
        )
        notes = list_promotable_notes(vault_root=str(self.vault))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["run_id"], "a")

    def test_empty_inbox(self) -> None:
        notes = list_promotable_notes(vault_root=str(self.vault))
        self.assertEqual(notes, [])

    def test_missing_inbox_dir(self) -> None:
        vault_empty = self.root / "vault_empty"
        vault_empty.mkdir()
        notes = list_promotable_notes(vault_root=str(vault_empty))
        self.assertEqual(notes, [])


# ---------------------------------------------------------------------------
# Action unit tests
# ---------------------------------------------------------------------------
class TestDraftPromoteActionUnit(unittest.TestCase):
    """Direct DraftPromoteAction tests — no broker overhead."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "Agent" / "Inbox_Agent"
        self.inbox.mkdir(parents=True)
        self.policy_path = _make_policy(
            self.root, vault_root=str(self.vault), action_enabled=True
        )
        self.policy = PolicyStore(self.policy_path)

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_not_configured_when_vault_root_empty(self) -> None:
        td2 = tempfile.TemporaryDirectory()
        try:
            p2 = _make_policy(Path(td2.name), vault_root="", action_enabled=True)
            policy2 = PolicyStore(p2)
            action = DraftPromoteAction(policy2)
            from actions import ActionError
            with self.assertRaises(ActionError) as ctx:
                action.execute({"note_name": INBOX_NOTE_NAME})
            self.assertEqual(ctx.exception.code, "not_configured")
        finally:
            td2.cleanup()

    def test_successful_promote_via_action(self) -> None:
        (self.inbox / INBOX_NOTE_NAME).write_text(
            _inbox_note_content(), encoding="utf-8"
        )
        action = DraftPromoteAction(self.policy)
        result = action.execute({"note_name": INBOX_NOTE_NAME})
        self.assertTrue(result.ok)
        self.assertEqual(result.result["note_name"], INBOX_NOTE_NAME)
        self.assertEqual(result.result["new_status"], "promoted_to_draft")

    def test_audit_params_only_note_name(self) -> None:
        action = DraftPromoteAction(self.policy)
        ap = action.audit_params({"note_name": "test.md"})
        self.assertEqual(ap, {"note_name": "test.md"})
        self.assertNotIn("body", str(ap))


# ---------------------------------------------------------------------------
# Telegram /draft_promote integration tests
# ---------------------------------------------------------------------------
class TestDraftPromoteTelegramCommand(unittest.TestCase):

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "Agent" / "Inbox_Agent"
        self.inbox.mkdir(parents=True)
        self.policy_path = _make_policy(
            self.root, vault_root=str(self.vault), action_enabled=True
        )
        self.fake_client = _FakeTelegramClient()
        self.proc = TelegramCommandProcessor(
            str(self.policy_path),
            api_client=self.fake_client,
        )

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_list_promotable_no_args(self) -> None:
        (self.inbox / INBOX_NOTE_NAME).write_text(
            _inbox_note_content(), encoding="utf-8"
        )
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="/draft_promote")
        self.assertIn("Notas promotables", reply)
        self.assertIn(INBOX_NOTE_NAME, reply)

    def test_list_empty_inbox(self) -> None:
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="/draft_promote")
        self.assertIn("No hay notas promotables", reply)

    def test_full_flow_confirmation_and_accept(self) -> None:
        (self.inbox / INBOX_NOTE_NAME).write_text(
            _inbox_note_content(), encoding="utf-8"
        )
        reply = self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text=f"/draft_promote note={INBOX_NOTE_NAME}",
        )
        self.assertIn("draft.promote", reply)
        self.assertIn(INBOX_NOTE_NAME, reply)
        reply2 = self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text="si",
        )
        self.assertIn("promovida", reply2.lower())
        # Verify evidence in vault
        self.assertTrue((self.inbox / "STAGED_INPUT.md").exists())
        source = (self.inbox / INBOX_NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("promoted_to_draft", source)

    def test_full_flow_confirmation_reject(self) -> None:
        (self.inbox / INBOX_NOTE_NAME).write_text(
            _inbox_note_content(), encoding="utf-8"
        )
        self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text=f"/draft_promote note={INBOX_NOTE_NAME}",
        )
        reply = self.proc.handle_text(chat_id="1001", user_id="", text="no")
        self.assertIn("cancelada", reply.lower())
        # Vault untouched
        self.assertFalse((self.inbox / "STAGED_INPUT.md").exists())
        source = (self.inbox / INBOX_NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("pending_triage", source)

    def test_viewer_cannot_promote(self) -> None:
        reply = self.proc.handle_text(
            chat_id="2002",
            user_id="",
            text=f"/draft_promote note={INBOX_NOTE_NAME}",
        )
        self.assertIn("no autorizado", reply.lower())

    def test_action_disabled_blocks_command(self) -> None:
        td2 = tempfile.TemporaryDirectory()
        try:
            root2 = Path(td2.name)
            vault2 = root2 / "vault"
            (vault2 / "Agent" / "Inbox_Agent").mkdir(parents=True)
            p2 = _make_policy(root2, vault_root=str(vault2), action_enabled=False)
            proc2 = TelegramCommandProcessor(
                str(p2), api_client=_FakeTelegramClient()
            )
            reply = proc2.handle_text(
                chat_id="1001",
                user_id="",
                text=f"/draft_promote note={INBOX_NOTE_NAME}",
            )
            self.assertIn("disabled", reply.lower())
        finally:
            td2.cleanup()

    def test_parse_missing_note_raises(self) -> None:
        from policy import PolicyError
        with self.assertRaises(PolicyError):
            TelegramCommandProcessor._parse_draft_promote_arguments("title=foo")

    def test_parse_valid_arguments(self) -> None:
        params = TelegramCommandProcessor._parse_draft_promote_arguments(
            f"note={INBOX_NOTE_NAME}"
        )
        self.assertEqual(params["note_name"], INBOX_NOTE_NAME)


if __name__ == "__main__":
    unittest.main()
