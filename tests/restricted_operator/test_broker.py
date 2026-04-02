from __future__ import annotations

import json
import io
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "scripts" / "agents" / "openclaw" / "restricted_operator"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from broker import RestrictedOperatorBroker  # noqa: E402
import cli as broker_cli  # noqa: E402
from models import BrokerRequest  # noqa: E402
from policy import PolicyStore  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402
from llm_adapter import LLMAdapter  # noqa: E402


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')

    def log_message(self, fmt: str, *args) -> None:
        return


class _FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str]] = []

    def send_message(self, *, chat_id: str, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class _FakeLLMAdapter:
    def __init__(self, *, enabled: bool = True, response: dict | None = None, error: Exception | None = None) -> None:
        self.enabled = enabled
        self.response = response or {
            "intent": "status",
            "action_id": "telegram.command",
            "params": {},
            "needs_confirmation": False,
            "reply_style": "brief",
        }
        self.error = error
        self.calls: list[str] = []

    def is_enabled(self) -> bool:
        return self.enabled

    def interpret(self, *, text: str) -> dict:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return dict(self.response)


class BrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.log_path = self.root / "logs" / "openclaw-current.log"
        self.audit_path = self.root / "audit" / "restricted_operator.jsonl"
        self.state_path = self.root / "state" / "restricted_operator_state.json"
        self.dropzone = self.root / "dropzone"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("line-1\nline-2\nline-3\n")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

        self.policy_path = self.root / "policy.json"
        self.policy_path.write_text(
            json.dumps(
                {
                    "broker": {
                        "bind_host": "127.0.0.1",
                        "bind_port": 18890,
                        "audit_log_path": str(self.audit_path),
                        "state_store_path": str(self.state_path),
                        "dropzone_dir": str(self.dropzone),
                        "max_tail_lines": 20,
                        "max_write_bytes": 128,
                    },
                    "actions": {
                        "action.health.general.v1": {"enabled": True, "mode": "readonly", "expires_at": None, "one_shot": False, "reason": "test", "updated_by": "test", "permission": "operator.read", "description": ""},
                        "action.logs.read.v1": {"enabled": True, "mode": "readonly", "expires_at": None, "one_shot": False, "reason": "test", "updated_by": "test", "permission": "operator.read", "description": ""},
                        "action.webhook.trigger.v1": {"enabled": True, "mode": "restricted", "expires_at": None, "one_shot": True, "reason": "test", "updated_by": "test", "permission": "operator.trigger", "description": ""},
                        "action.openclaw.restart.v1": {"enabled": False, "mode": "restricted", "expires_at": None, "one_shot": False, "reason": "test", "updated_by": "test", "permission": "operator.control", "description": ""},
                        "action.dropzone.write.v1": {"enabled": True, "mode": "restricted", "expires_at": None, "one_shot": False, "reason": "test", "updated_by": "test", "permission": "operator.write", "description": ""}
                    },
                    "operator_auth": {
                        "roles": {
                            "viewer": ["policy.read", "operator.read"],
                            "operator": ["policy.read", "policy.mutate", "operator.read", "operator.trigger", "operator.write"],
                            "admin": ["policy.read", "policy.mutate", "operator.audit", "operator.read", "operator.trigger", "operator.write", "operator.control"],
                        },
                        "operators": {
                            "authorized-operator": {
                                "role": "operator",
                                "enabled": True,
                                "display_name": "Authorized Operator",
                                "reason": "test_operator",
                            },
                            "readonly-viewer": {
                                "role": "viewer",
                                "enabled": True,
                                "display_name": "Readonly Viewer",
                                "reason": "test_viewer",
                            },
                            "admin-operator": {
                                "role": "admin",
                                "enabled": True,
                                "display_name": "Admin Operator",
                                "reason": "test_admin",
                            },
                        },
                    },
                    "telegram": {
                        "enabled": True,
                        "bot_token_env": "OPENCLAW_TELEGRAM_BOT_TOKEN",
                        "api_base_url": "https://api.telegram.org",
                        "poll_timeout_seconds": 1,
                        "audit_tail_lines": 5,
                        "offset_store_path": str(self.root / "state" / "telegram_offset.json"),
                        "runtime_status_path": str(self.root / "state" / "telegram_runtime_status.json"),
                        "rate_limit_window_seconds": 30,
                        "rate_limit_max_requests": 6,
                        "max_command_length": 512,
                        "allowed_chats": {
                            "1001": {
                                "operator_id": "authorized-operator",
                                "enabled": True,
                                "display_name": "Authorized Chat",
                                "reason": "test",
                            },
                            "2002": {
                                "operator_id": "readonly-viewer",
                                "enabled": True,
                                "display_name": "Readonly Chat",
                                "reason": "test",
                            }
                        },
                        "allowed_users": {}
                    },
                    "health_checks": {
                        "local_ok": {"url": f"{self.base_url}/healthz", "expect_status": 200}
                    },
                    "log_streams": {
                        "openclaw_runtime": {
                            "path": str(self.log_path),
                            "tail_lines_default": 2
                        }
                    },
                    "webhook_targets": {
                        "controlled": {
                            "url": f"{self.base_url}/hook",
                            "method": "POST",
                            "timeout_seconds": 5
                        }
                    }
                }
            )
        )
        self.broker = RestrictedOperatorBroker(str(self.policy_path))
        self.telegram_client = _FakeTelegramClient()
        self.telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client)

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tempdir.cleanup()

    def test_health_action(self) -> None:
        result = self.broker.execute(BrokerRequest(action_id="action.health.general.v1"))
        self.assertTrue(result.ok)
        self.assertEqual(result.result["checks"]["local_ok"]["status"], 200)
        audit_lines = self.audit_path.read_text().strip().splitlines()
        self.assertEqual(json.loads(audit_lines[-1])["event"], "action_executed")

    def test_logs_action(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.logs.read.v1",
                params={"stream_id": "openclaw_runtime", "tail_lines": 2},
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.result["lines"], ["line-2", "line-3"])

    def test_dropzone_write_rejects_traversal(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.dropzone.write.v1",
                params={"filename": "../bad.txt", "content": "hello"},
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "invalid_params")

    def test_webhook_action(self) -> None:
        result = self.broker.execute(
            BrokerRequest(
                action_id="action.webhook.trigger.v1",
                params={"target_id": "controlled", "event_type": "ping", "note": "test"},
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.result["status"], 200)
        state = PolicyStore(str(self.policy_path))
        effective = state.get_effective_action_state("action.webhook.trigger.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "consumed")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("action_consumed_one_shot", audit_events)

    def test_disabled_restart_action(self) -> None:
        result = self.broker.execute(BrokerRequest(action_id="action.openclaw.restart.v1"))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "forbidden")
        self.assertEqual(result.event, "action_rejected_disabled")

    def test_expired_action_is_rejected(self) -> None:
        payload = json.loads(self.policy_path.read_text())
        payload["actions"]["action.dropzone.write.v1"]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat().replace("+00:00", "Z")
        self.policy_path.write_text(json.dumps(payload))
        broker = RestrictedOperatorBroker(str(self.policy_path))
        result = broker.execute(
            BrokerRequest(
                action_id="action.dropzone.write.v1",
                params={"filename": "ok.txt", "content": "hello"},
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.event, "action_rejected_expired")

    def test_policy_validation_rejects_invalid_mode(self) -> None:
        payload = json.loads(self.policy_path.read_text())
        payload["actions"]["action.logs.read.v1"]["mode"] = "invalid"
        self.policy_path.write_text(json.dumps(payload))
        ok, errors = PolicyStore.validate_policy(self.policy_path)
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_policy_validation_rejects_unknown_operator_role(self) -> None:
        payload = json.loads(self.policy_path.read_text())
        payload["operator_auth"]["operators"]["authorized-operator"]["role"] = "unknown-role"
        self.policy_path.write_text(json.dumps(payload))
        ok, errors = PolicyStore.validate_policy(self.policy_path)
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_policy_store_can_enable_disable_and_ttl(self) -> None:
        store = PolicyStore(str(self.policy_path))
        store.authorize_operator("authorized-operator", "policy.mutate")
        store.set_action_enabled("action.dropzone.write.v1", enabled=False, updated_by="tester", reason="disable")
        disabled = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(disabled)
        self.assertEqual(disabled.status, "disabled")
        expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        store.set_action_enabled("action.dropzone.write.v1", enabled=True, updated_by="tester", reason="enable")
        store.set_action_expiration("action.dropzone.write.v1", expires_at=expiry, updated_by="tester", reason="ttl")
        enabled = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(enabled)
        self.assertEqual(enabled.status, "enabled")
        self.assertIsNotNone(enabled.expires_at)

    def test_policy_store_can_reset_one_shot(self) -> None:
        store = PolicyStore(str(self.policy_path))
        store.mark_one_shot_used("action.webhook.trigger.v1", updated_by="tester", reason="consume")
        consumed = store.get_effective_action_state("action.webhook.trigger.v1")
        self.assertIsNotNone(consumed)
        self.assertEqual(consumed.status, "consumed")
        store.reset_one_shot("action.webhook.trigger.v1", updated_by="tester", reason="reset")
        reset = store.get_effective_action_state("action.webhook.trigger.v1")
        self.assertIsNotNone(reset)
        self.assertEqual(reset.status, "enabled")

    def test_policy_store_refreshes_runtime_state_for_long_lived_instances(self) -> None:
        observer = PolicyStore(str(self.policy_path))
        writer = PolicyStore(str(self.policy_path))

        writer.set_action_enabled(
            "action.dropzone.write.v1",
            enabled=False,
            updated_by="tester",
            reason="refresh_visibility",
        )

        effective = observer.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "disabled")

    def test_concurrent_runtime_state_mutations_do_not_lose_updates(self) -> None:
        first_store = PolicyStore(str(self.policy_path))
        second_store = PolicyStore(str(self.policy_path))
        start_barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def disable_dropzone() -> None:
            try:
                start_barrier.wait()
                first_store.set_action_enabled(
                    "action.dropzone.write.v1",
                    enabled=False,
                    updated_by="tester-a",
                    reason="concurrent_disable",
                )
            except Exception as exc:  # pragma: no cover - defensive path for thread failures
                errors.append(exc)

        def enable_restart() -> None:
            try:
                start_barrier.wait()
                second_store.set_action_enabled(
                    "action.openclaw.restart.v1",
                    enabled=True,
                    updated_by="tester-b",
                    reason="concurrent_enable",
                )
            except Exception as exc:  # pragma: no cover - defensive path for thread failures
                errors.append(exc)

        threads = [
            threading.Thread(target=disable_dropzone),
            threading.Thread(target=enable_restart),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        store = PolicyStore(str(self.policy_path))
        dropzone = store.get_effective_action_state("action.dropzone.write.v1")
        restart = store.get_effective_action_state("action.openclaw.restart.v1")
        self.assertIsNotNone(dropzone)
        self.assertIsNotNone(restart)
        self.assertEqual(dropzone.status, "disabled")
        self.assertEqual(restart.status, "enabled")

    def test_authorized_operator_can_change_policy(self) -> None:
        rc = broker_cli.set_enabled(
            str(self.policy_path),
            "action.dropzone.write.v1",
            False,
            "authorized-operator",
            "authorized-operator",
            "authorized_disable",
        )
        self.assertEqual(rc, 0)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "disabled")

    def test_enable_with_invalid_ttl_does_not_leave_partial_mutation(self) -> None:
        payload = json.loads(self.policy_path.read_text())
        payload["actions"]["action.dropzone.write.v1"]["enabled"] = False
        self.policy_path.write_text(json.dumps(payload))
        rc = broker_cli.enable_with_optional_ttl(
            str(self.policy_path),
            "action.dropzone.write.v1",
            ttl_minutes=None,
            expires_at="not-a-datetime",
            operator_id="authorized-operator",
            updated_by="authorized-operator",
            reason="broken_ttl_attempt",
        )
        self.assertEqual(rc, 1)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "disabled")

    def test_enable_with_ttl_sets_enabled_and_expiration_atomically(self) -> None:
        payload = json.loads(self.policy_path.read_text())
        payload["actions"]["action.dropzone.write.v1"]["enabled"] = False
        self.policy_path.write_text(json.dumps(payload))
        rc = broker_cli.enable_with_optional_ttl(
            str(self.policy_path),
            "action.dropzone.write.v1",
            ttl_minutes=15,
            expires_at=None,
            operator_id="authorized-operator",
            updated_by="authorized-operator",
            reason="enable_with_ttl",
        )
        self.assertEqual(rc, 0)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")
        self.assertIsNotNone(effective.expires_at)

    def test_unauthorized_operator_cannot_change_policy(self) -> None:
        rc = broker_cli.set_enabled(
            str(self.policy_path),
            "action.dropzone.write.v1",
            False,
            "unknown-operator",
            "unknown-operator",
            "unauthorized_disable",
        )
        self.assertEqual(rc, 1)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("operator_authorization_rejected", audit_events)

    def test_readonly_show_is_permitted_without_authorization(self) -> None:
        store = PolicyStore(str(self.policy_path))
        output = io.StringIO()
        with redirect_stdout(output):
            rc = broker_cli.dump_states(store, None, "json")
        self.assertEqual(rc, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("actions", payload)
        self.assertTrue(any(item["action_id"] == "action.health.general.v1" for item in payload["actions"]))

    def test_console_show_output_is_human_readable(self) -> None:
        store = PolicyStore(str(self.policy_path))
        output = io.StringIO()
        with redirect_stdout(output):
            rc = broker_cli.dump_states(store, None, "console")
        self.assertEqual(rc, 0)
        rendered = output.getvalue()
        self.assertIn("scope=restricted_operator_capabilities", rendered)
        self.assertIn("action.health.general.v1", rendered)
        self.assertIn("allowed=yes", rendered)

    def test_viewer_cannot_change_policy(self) -> None:
        rc = broker_cli.set_ttl(
            str(self.policy_path),
            "action.dropzone.write.v1",
            ttl_minutes=15,
            expires_at=None,
            operator_id="readonly-viewer",
            updated_by="readonly-viewer",
            reason="viewer_attempt",
        )
        self.assertEqual(rc, 1)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertIsNone(effective.expires_at)

    def test_operator_cannot_enable_control_action(self) -> None:
        rc = broker_cli.set_enabled(
            str(self.policy_path),
            "action.openclaw.restart.v1",
            True,
            "authorized-operator",
            "authorized-operator",
            "unauthorized_control_enable",
        )
        self.assertEqual(rc, 1)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.openclaw.restart.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "disabled")

    def test_admin_can_enable_control_action(self) -> None:
        rc = broker_cli.set_enabled(
            str(self.policy_path),
            "action.openclaw.restart.v1",
            True,
            "admin-operator",
            "admin-operator",
            "authorized_control_enable",
        )
        self.assertEqual(rc, 0)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.openclaw.restart.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")

    def test_telegram_status_for_authorized_chat(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="/status")
        self.assertIn("actions_total=", reply)
        self.assertIn("operator=authorized-operator", reply)

    def test_telegram_conversational_status_intent(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="estado general")
        self.assertIn("actions_total=", reply)
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("intent_detected", audit_events)

    def test_telegram_conversational_capabilities_intent(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="capacidades activas")
        self.assertIn("action.health.general.v1", reply)
        self.assertIn("exec=yes", reply)

    def test_telegram_wake_starts_assistant_session(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        self.assertIn("Asistente despierto.", reply)
        self.assertTrue(self.telegram._has_active_session(chat_id="1001", user_id="42", operator_id="authorized-operator"))
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("assistant_wake", audit_events)

    def test_telegram_sleep_ends_assistant_session(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="/sleep")
        self.assertIn("Asistente dormido.", reply)
        self.assertFalse(self.telegram._has_active_session(chat_id="1001", user_id="42", operator_id="authorized-operator"))
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("assistant_sleep", audit_events)

    def test_telegram_wake_timeout_expires_session(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        session_key = self.telegram._session_key(chat_id="1001", user_id="42")
        self.telegram.assistant_idle_timeout_seconds = 60
        self.telegram.assistant_sessions[session_key].last_activity_at -= 120
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="haz algo inteligente con el sistema")
        self.assertIn("No entendí la intención", reply)
        self.assertFalse(self.telegram._has_active_session(chat_id="1001", user_id="42", operator_id="authorized-operator"))
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("assistant_sleep", audit_events)

    def test_telegram_awake_mode_accepts_natural_status_query(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="como estamos")
        self.assertIn("Estado general de OpenClaw:", reply)
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("response_generated", audit_events)

    def test_telegram_awake_mode_accepts_capabilities_query_with_punctuation(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="que puedes hacer?")
        self.assertIn("Capacidades activas y visibles para este operador:", reply)

    def test_telegram_awake_mode_accepts_identity_query(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="quien eres?")
        self.assertIn("Soy el asistente controlado de OpenClaw", reply)

    def test_telegram_prudent_suggestion_is_conservative(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(
            chat_id="1001",
            user_id="42",
            text="que propones para mejorar la operacion sin tocar nada sensible?",
        )
        self.assertIn("Propuesta prudente:", reply)
        self.assertIn("auditoría", reply.lower())
        self.assertNotIn("restart", reply.lower())
        self.assertNotIn("habilitar ", reply.lower())
        self.assertNotIn("action.openclaw.restart.v1", reply.lower())

    def test_telegram_conceptual_explain_status_is_not_generic_status_block(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(
            chat_id="1001",
            user_id="42",
            text="explicame brevemente que significa que haya una capacidad expirada y otra deshabilitada",
        )
        self.assertIn("enabled", reply)
        self.assertIn("disabled", reply)
        self.assertIn("expired", reply)
        self.assertIn("one-shot", reply)
        self.assertNotIn("Estado general de OpenClaw:", reply)

    def test_telegram_awake_unknown_phrase_invokes_llm(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "status",
                "action_id": "telegram.command",
                "params": {},
                "needs_confirmation": False,
                "reply_style": "brief",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="dame una lectura rápida de cómo pinta todo hoy")
        self.assertIn("Estado general de OpenClaw:", reply)
        self.assertEqual(llm.calls, ["dame una lectura rápida de cómo pinta todo hoy"])
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("llm_invoked", audit_events)
        self.assertIn("llm_output_validated", audit_events)

    def test_telegram_known_prudent_suggestion_phrase_stays_local_first(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "enable_capability",
                "action_id": "action.openclaw.restart.v1",
                "params": {},
                "needs_confirmation": True,
                "reply_style": "brief",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(
            chat_id="1001",
            user_id="42",
            text="que propones para mejorar la operacion sin tocar nada sensible?",
        )
        self.assertIn("Propuesta prudente:", reply)
        self.assertEqual(llm.calls, [])

    def test_telegram_sleep_mode_does_not_invoke_llm(self) -> None:
        llm = _FakeLLMAdapter()
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="dame una lectura rápida de cómo pinta todo hoy")
        self.assertIn("No entendí la intención", reply)
        self.assertEqual(llm.calls, [])

    def test_telegram_slash_command_does_not_invoke_llm(self) -> None:
        llm = _FakeLLMAdapter()
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="/status")
        self.assertIn("actions_total=", reply)
        self.assertEqual(llm.calls, [])

    def test_telegram_confirmation_does_not_invoke_llm(self) -> None:
        llm = _FakeLLMAdapter()
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="deshabilita action.dropzone.write.v1")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="si")
        self.assertIn("Acción aplicada.", reply)
        self.assertEqual(llm.calls, [])

    def test_telegram_llm_invalid_output_falls_back_safely(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "status",
                "action_id": "telegram.command",
                "params": {},
                "needs_confirmation": False,
                "reply_style": "brief",
                "extra": "forbidden",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="haz algo inteligente con el sistema")
        self.assertIn("No puedo interpretar esa frase de forma segura.", reply)
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("llm_output_rejected", audit_events)

    def test_telegram_llm_rejects_intent_outside_allowlist(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "run_shell",
                "action_id": "telegram.command",
                "params": {},
                "needs_confirmation": False,
                "reply_style": "brief",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="haz algo inteligente con el sistema")
        self.assertIn("No puedo interpretar esa frase de forma segura.", reply)
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("llm_output_rejected", audit_events)

    def test_telegram_llm_valid_read_still_obeys_auth(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "audit_tail",
                "action_id": "telegram.command",
                "params": {},
                "needs_confirmation": False,
                "reply_style": "brief",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="2002", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="2002", user_id="42", text="cuéntame lo último importante")
        self.assertEqual(reply, "Operador no autorizado para consultar auditoría.")
        self.assertEqual(llm.calls, ["cuéntame lo último importante"])

    def test_telegram_llm_valid_mutation_requires_confirmation(self) -> None:
        llm = _FakeLLMAdapter(
            response={
                "intent": "disable_capability",
                "action_id": "action.dropzone.write.v1",
                "params": {},
                "needs_confirmation": True,
                "reply_style": "brief",
            }
        )
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="quita acceso de escritura al dropzone por ahora")
        self.assertIn("Acción interpretada:", reply)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")

    def test_telegram_disabled_llm_preserves_existing_fallback(self) -> None:
        llm = _FakeLLMAdapter(enabled=False)
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client, llm_adapter=llm)
        telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = telegram.handle_text(chat_id="1001", user_id="42", text="haz algo inteligente con el sistema")
        self.assertIn("No puedo interpretar esa frase de forma segura.", reply)
        self.assertEqual(llm.calls, [])

    def test_llm_adapter_ignores_invalid_timeout_when_disabled(self) -> None:
        previous_enabled = os.environ.get("OPENCLAW_LLM_ENABLED")
        previous_timeout = os.environ.get("OPENCLAW_LLM_TIMEOUT_SECONDS")
        self.addCleanup(self._restore_env_var, "OPENCLAW_LLM_ENABLED", previous_enabled)
        self.addCleanup(self._restore_env_var, "OPENCLAW_LLM_TIMEOUT_SECONDS", previous_timeout)
        os.environ["OPENCLAW_LLM_ENABLED"] = "false"
        os.environ["OPENCLAW_LLM_TIMEOUT_SECONDS"] = "invalid"
        adapter = LLMAdapter()
        self.assertFalse(adapter.is_enabled())

    @staticmethod
    def _restore_env_var(key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def test_telegram_conversational_mutation_requires_confirmation(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="deshabilita action.dropzone.write.v1")
        self.assertIn("Acción interpretada:", reply)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("confirmation_requested", audit_events)

    def test_telegram_conversational_mutation_executes_after_confirmation(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="deshabilita action.dropzone.write.v1")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="si")
        self.assertIn("Acción aplicada.", reply)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "disabled")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("confirmation_accepted", audit_events)
        self.assertIn("action_executed", audit_events)

    def test_telegram_awake_mutation_still_requires_confirmation(self) -> None:
        self.telegram.handle_text(chat_id="1001", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="deshabilita action.dropzone.write.v1")
        self.assertIn("Acción interpretada:", reply)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")

    def test_telegram_awake_mutation_rejected_for_operator_without_permissions(self) -> None:
        self.telegram.handle_text(chat_id="2002", user_id="42", text="/wake")
        reply = self.telegram.handle_text(chat_id="2002", user_id="42", text="deshabilita action.dropzone.write.v1")
        self.assertIn("No puedo proponer esa acción", reply)
        store = PolicyStore(str(self.policy_path))
        effective = store.get_effective_action_state("action.dropzone.write.v1")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status, "enabled")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("intent_rejected_unauthorized", audit_events)

    def test_telegram_conversational_rejects_unsupported_intent(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="haz algo inteligente con el sistema")
        self.assertIn("No entendí la intención", reply)
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("intent_rejected_unsupported", audit_events)

    def test_telegram_rejects_unauthorized_chat(self) -> None:
        reply = self.telegram.handle_text(chat_id="9999", user_id="42", text="/status")
        self.assertEqual(reply, "Chat no autorizado para este bot.")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("telegram_command_rejected_unauthorized_chat", audit_events)

    def test_telegram_execute_health_for_authorized_operator(self) -> None:
        reply = self.telegram.handle_text(chat_id="1001", user_id="42", text="/execute action.health.general.v1")
        self.assertIn('"ok": true', reply.lower())
        self.assertIn("action.health.general.v1", reply)

    def test_telegram_execute_rejected_for_viewer_on_write_action(self) -> None:
        reply = self.telegram.handle_text(
            chat_id="2002",
            user_id="42",
            text="/execute action.dropzone.write.v1 filename=note.txt content=hello",
        )
        self.assertEqual(reply, "Operador no autorizado para action.dropzone.write.v1.")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("telegram_command_rejected_operator_not_authorized", audit_events)

    def test_telegram_audit_tail_requires_admin(self) -> None:
        viewer_reply = self.telegram.handle_text(chat_id="2002", user_id="42", text="/audit_tail")
        self.assertEqual(viewer_reply, "Operador no autorizado para consultar auditoría.")
        payload = json.loads(self.policy_path.read_text())
        payload["telegram"]["allowed_chats"]["3003"] = {
            "operator_id": "admin-operator",
            "enabled": True,
            "display_name": "Admin Chat",
            "reason": "test_admin_chat",
        }
        self.policy_path.write_text(json.dumps(payload))
        telegram = TelegramCommandProcessor(str(self.policy_path), api_client=self.telegram_client)
        admin_reply = telegram.handle_text(chat_id="3003", user_id="7", text="/audit_tail")
        self.assertTrue("No hay eventos" in admin_reply or "telegram_command" in admin_reply or "action=" in admin_reply)

    def test_telegram_rate_limit_rejects_burst(self) -> None:
        self.telegram.rate_limiter.max_requests = 2
        update1 = {"update_id": 1, "message": {"chat": {"id": 1001}, "from": {"id": 42}, "text": "/status"}}
        update2 = {"update_id": 2, "message": {"chat": {"id": 1001}, "from": {"id": 42}, "text": "/status"}}
        update3 = {"update_id": 3, "message": {"chat": {"id": 1001}, "from": {"id": 42}, "text": "/status"}}
        self.telegram.process_update(update1)
        self.telegram.process_update(update2)
        self.telegram.process_update(update3)
        self.assertEqual(self.telegram_client.sent_messages[-1][1], "Rate limit activo. Espera unos segundos y reintenta.")
        audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
        self.assertIn("telegram_command_rejected_rate_limited", audit_events)

    def test_telegram_edited_message_does_not_reexecute_action(self) -> None:
        update = {
            "update_id": 55,
            "edited_message": {
                "chat": {"id": 1001},
                "from": {"id": 42},
                "text": "/execute action.health.general.v1",
            },
        }
        handled_update_id = self.telegram.process_update(update)
        self.assertEqual(handled_update_id, 55)
        self.assertEqual(self.telegram_client.sent_messages, [])
        if self.audit_path.exists():
            audit_events = [json.loads(line)["event"] for line in self.audit_path.read_text().strip().splitlines()]
            self.assertNotIn("telegram_action_requested", audit_events)

    def test_console_audit_tail_empty_is_human_readable(self) -> None:
        if self.audit_path.exists():
            self.audit_path.unlink()
        output = io.StringIO()
        with redirect_stdout(output):
            rc = broker_cli.audit_tail(str(self.policy_path), 5, "console")
        self.assertEqual(rc, 0)
        rendered = output.getvalue()
        self.assertIn("scope=restricted_operator_audit", rendered)
        self.assertIn("no_events=yes", rendered)


if __name__ == "__main__":
    unittest.main()
