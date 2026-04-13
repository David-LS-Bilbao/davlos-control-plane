from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "agents" / "openclaw" / "restricted_operator"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from actions import InboxWriteAction  # noqa: E402
from broker import RestrictedOperatorBroker  # noqa: E402
from models import BrokerRequest  # noqa: E402
from policy import PolicyStore  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402


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


class TestInboxWriteActionUnit(unittest.TestCase):
    """Direct InboxWriteAction tests — no broker overhead."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
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
            action = InboxWriteAction(policy2)
            from actions import ActionError
            with self.assertRaises(ActionError) as ctx:
                action.execute(
                    {"run_id": "r1", "capture_title": "T", "capture_body": "B"}
                )
            self.assertEqual(ctx.exception.code, "not_configured")
        finally:
            td2.cleanup()

    def test_destination_missing_raises(self) -> None:
        # vault exists but Agent/Inbox_Agent does not
        self.vault.mkdir(parents=True, exist_ok=True)
        action = InboxWriteAction(self.policy)
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            action.execute(
                {"run_id": "r1", "capture_title": "T", "capture_body": "B"}
            )
        self.assertEqual(ctx.exception.code, "destination_missing")

    def test_successful_write(self) -> None:
        (self.vault / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
        action = InboxWriteAction(self.policy)
        result = action.execute(
            {"run_id": "test-001", "capture_title": "Test Title", "capture_body": "Body text."}
        )
        self.assertTrue(result.ok)
        self.assertIn("note_name", result.result)
        self.assertIn("note_path", result.result)
        self.assertGreater(result.result["bytes_written"], 0)
        self.assertTrue(Path(result.result["note_path"]).exists())

    def test_audit_params_excludes_body(self) -> None:
        action = InboxWriteAction(self.policy)
        ap = action.audit_params(
            {
                "run_id": "r1",
                "capture_title": "T",
                "capture_body": "Hello world",
                "source_refs": ["ref1", "ref2"],
            }
        )
        self.assertNotIn("capture_body", ap)
        self.assertEqual(ap["body_bytes"], len("Hello world".encode("utf-8")))
        self.assertEqual(ap["source_refs_count"], 2)
        self.assertEqual(ap["run_id"], "r1")
        self.assertEqual(ap["capture_title"], "T")

    def test_invalid_run_id_raises(self) -> None:
        (self.vault / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
        action = InboxWriteAction(self.policy)
        from actions import ActionError
        with self.assertRaises(ActionError):
            action.execute(
                {"run_id": "", "capture_title": "T", "capture_body": "B"}
            )

    def test_source_refs_not_list_raises(self) -> None:
        (self.vault / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
        action = InboxWriteAction(self.policy)
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            action.execute(
                {
                    "run_id": "r1",
                    "capture_title": "T",
                    "capture_body": "B",
                    "source_refs": "not-a-list",
                }
            )
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_create_only_rejects_duplicate(self) -> None:
        (self.vault / "Agent" / "Inbox_Agent").mkdir(parents=True, exist_ok=True)
        action = InboxWriteAction(self.policy)
        result1 = action.execute(
            {"run_id": "dup-001", "capture_title": "T", "capture_body": "B"}
        )
        self.assertTrue(result1.ok)
        from actions import ActionError
        with self.assertRaises(ActionError) as ctx:
            action.execute(
                {"run_id": "dup-001", "capture_title": "T", "capture_body": "B"}
            )
        self.assertEqual(ctx.exception.code, "write_failed")


class TestInboxWriteTelegramCommand(unittest.TestCase):
    """Telegram /inbox_write command integration tests."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.vault = self.root / "vault"
        (self.vault / "Agent" / "Inbox_Agent").mkdir(parents=True)
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

    def test_parse_valid_inbox_write(self) -> None:
        params = TelegramCommandProcessor._parse_inbox_write_arguments(
            "run_id=tg-001 title=Mi+Titulo :: Cuerpo de la captura"
        )
        self.assertEqual(params["run_id"], "tg-001")
        self.assertEqual(params["capture_title"], "Mi Titulo")
        self.assertEqual(params["capture_body"], "Cuerpo de la captura")
        self.assertIsNone(params["source_refs"])

    def test_parse_missing_separator_raises(self) -> None:
        from policy import PolicyError
        with self.assertRaises(PolicyError):
            TelegramCommandProcessor._parse_inbox_write_arguments("run_id=r1 title=T")

    def test_parse_empty_body_raises(self) -> None:
        from policy import PolicyError
        with self.assertRaises(PolicyError):
            TelegramCommandProcessor._parse_inbox_write_arguments("run_id=r1 title=T :: ")

    def test_parse_missing_run_id_raises(self) -> None:
        from policy import PolicyError
        with self.assertRaises(PolicyError):
            TelegramCommandProcessor._parse_inbox_write_arguments("title=T :: Body")

    def test_parse_source_refs(self) -> None:
        params = TelegramCommandProcessor._parse_inbox_write_arguments(
            "run_id=r1 title=T source_refs=ref1,ref2 :: Body"
        )
        self.assertEqual(params["source_refs"], ["ref1", "ref2"])

    def test_full_flow_confirmation_and_accept(self) -> None:
        reply = self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text="/inbox_write run_id=flow-001 title=Test :: Captura de prueba",
        )
        self.assertIn("inbox.write", reply)
        self.assertIn("flow-001", reply)
        reply2 = self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text="si",
        )
        self.assertIn("Captura guardada", reply2)

    def test_full_flow_confirmation_reject(self) -> None:
        self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text="/inbox_write run_id=rej-001 title=T :: Body",
        )
        reply = self.proc.handle_text(
            chat_id="1001",
            user_id="",
            text="no",
        )
        self.assertIn("cancelada", reply.lower())

    def test_viewer_cannot_invoke_inbox_write(self) -> None:
        reply = self.proc.handle_text(
            chat_id="2002",
            user_id="",
            text="/inbox_write run_id=v-001 title=T :: Body",
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
                text="/inbox_write run_id=dis-001 title=T :: Body",
            )
            self.assertIn("disabled", reply.lower())
        finally:
            td2.cleanup()


if __name__ == "__main__":
    unittest.main()
