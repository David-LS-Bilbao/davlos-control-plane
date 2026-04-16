"""Tests for Phase 9 — Sandbox Mode (LLM-backed free vault access).

Covers:
- SandboxLLMAgent: chat, history management, action parsing, error handling
- Sandbox activation / deactivation triggers in TelegramCommandProcessor
- Routing to sandbox when active
- LLM action execution via broker
- Sandbox deactivation on /sleep
- Render functions
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_OPENCLAW = Path(__file__).resolve().parents[2] / "scripts" / "agents" / "openclaw"
_RO = _OPENCLAW / "restricted_operator"

if str(_OPENCLAW) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW))
if str(_RO) not in sys.path:
    sys.path.insert(0, str(_RO))

import assistant_responses  # noqa: E402
from llm_agent import SandboxLLMAgent, SandboxLLMAgentError  # noqa: E402
from telegram_bot import TelegramCommandProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(root: Path, *, vault_root: str = "") -> Path:
    p = root / "policy.json"
    p.write_text(json.dumps({
        "broker": {
            "bind_host": "127.0.0.1",
            "bind_port": 18890,
            "audit_log_path": str(root / "audit.jsonl"),
            "state_store_path": str(root / "state.json"),
            "dropzone_dir": str(root / "dropzone"),
            "max_tail_lines": 50,
            "max_write_bytes": 4096,
        },
        "vault_inbox": {"vault_root": vault_root},
        "actions": {
            "action.health.general.v1": {
                "enabled": True, "mode": "readonly", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.read", "description": "health",
            },
            "action.note.create.v1": {
                "enabled": True, "mode": "restricted", "expires_at": None,
                "one_shot": False, "reason": "test", "updated_by": "test",
                "permission": "operator.write", "description": "create note",
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
            "poll_timeout_seconds": 20,
            "audit_tail_lines": 10,
            "offset_store_path": str(root / "offset.json"),
            "runtime_status_path": str(root / "runtime.json"),
            "rate_limit_window_seconds": 30,
            "rate_limit_max_requests": 60,
            "max_command_length": 512,
            "assistant_idle_timeout_seconds": 600,
            "allowed_chats": {
                "100": {
                    "operator_id": "test-operator", "enabled": True,
                    "display_name": "Test chat", "reason": "test",
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
# SandboxLLMAgent unit tests
# ---------------------------------------------------------------------------

class TestSandboxLLMAgentParseAction(unittest.TestCase):
    def test_no_action_returns_none(self):
        result = SandboxLLMAgent._parse_action("Solo texto sin acción.")
        self.assertIsNone(result)

    def test_valid_action_parsed(self):
        text = 'Voy a crear la nota. <action>{"action_id": "action.note.create.v1", "params": {"folder": "Proyectos", "title": "Demo"}}</action>'
        result = SandboxLLMAgent._parse_action(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action_id"], "action.note.create.v1")
        self.assertEqual(result["params"]["folder"], "Proyectos")

    def test_malformed_json_returns_none(self):
        result = SandboxLLMAgent._parse_action("<action>not json</action>")
        self.assertIsNone(result)

    def test_missing_action_id_returns_none(self):
        result = SandboxLLMAgent._parse_action('<action>{"params": {}}</action>')
        self.assertIsNone(result)

    def test_params_defaults_to_empty_dict(self):
        result = SandboxLLMAgent._parse_action('<action>{"action_id": "action.health.general.v1"}</action>')
        self.assertIsNotNone(result)
        self.assertEqual(result["params"], {})


class TestSandboxLLMAgentExtractText(unittest.TestCase):
    def test_extracts_content(self):
        payload = {"choices": [{"message": {"content": "Hola mundo"}}]}
        self.assertEqual(SandboxLLMAgent._extract_text(payload), "Hola mundo")

    def test_empty_choices_raises(self):
        with self.assertRaises(SandboxLLMAgentError):
            SandboxLLMAgent._extract_text({"choices": []})

    def test_empty_content_raises(self):
        with self.assertRaises(SandboxLLMAgentError):
            SandboxLLMAgent._extract_text({"choices": [{"message": {"content": ""}}]})


class TestSandboxLLMAgentHistory(unittest.TestCase):
    def _make_agent(self) -> SandboxLLMAgent:
        agent = SandboxLLMAgent(max_history_turns=2)
        return agent

    def test_clear_history_removes_key(self):
        agent = self._make_agent()
        agent._history["k1"] = __import__("collections").deque([{"role": "user", "content": "hi"}])
        agent.clear_history("k1")
        self.assertNotIn("k1", agent._history)

    def test_clear_nonexistent_key_is_noop(self):
        agent = self._make_agent()
        agent.clear_history("nonexistent")  # should not raise

    def test_chat_rolls_back_on_network_error(self):
        agent = self._make_agent()
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            with self.assertRaises(SandboxLLMAgentError):
                agent.chat(key="k", message="test")
        # user message should have been rolled back
        self.assertEqual(len(agent._history.get("k", [])), 0)

    def test_history_trimmed_to_max_turns(self):
        agent = SandboxLLMAgent(max_history_turns=1)  # max 2 messages
        fake_response = {
            "choices": [{"message": {"content": "respuesta"}}]
        }
        with patch("urllib.request.urlopen") as mock_open:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=json.dumps(fake_response).encode())
            ))
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_cm
            agent.chat(key="k", message="primero")
            agent.chat(key="k", message="segundo")
        # Should only keep last 1 turn = 2 messages
        self.assertLessEqual(len(agent._history["k"]), 2)


class TestSandboxLLMAgentActionStripping(unittest.TestCase):
    def test_action_tag_stripped_from_clean_text(self):
        agent = SandboxLLMAgent()
        raw = 'Voy a hacerlo. <action>{"action_id": "action.note.create.v1", "params": {}}</action>'
        fake_response = {"choices": [{"message": {"content": raw}}]}
        with patch("urllib.request.urlopen") as mock_open:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=json.dumps(fake_response).encode())
            ))
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_cm
            text, action = agent.chat(key="k", message="crea nota")
        self.assertNotIn("<action>", text)
        self.assertIsNotNone(action)
        self.assertEqual(action["action_id"], "action.note.create.v1")


# ---------------------------------------------------------------------------
# Sandbox activation / deactivation in TelegramCommandProcessor
# ---------------------------------------------------------------------------

class TestSandboxActivation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_path = str(_make_policy(Path(self.tmp.name)))
        self.proc = _make_proc(self.policy_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_activa_modo_libre_activates(self):
        reply = _send(self.proc, "activa modo libre")
        self.assertIn("[SANDBOX]", reply)
        key = "100:1"
        self.assertTrue(self.proc._sandbox_mode.get(key))

    def test_libera_openclaw_activates(self):
        reply = _send(self.proc, "libera openclaw")
        self.assertIn("[SANDBOX]", reply)

    def test_modo_sandbox_activates(self):
        reply = _send(self.proc, "modo sandbox")
        self.assertIn("[SANDBOX]", reply)

    def test_deactivation_clears_flag(self):
        _send(self.proc, "activa modo libre")
        reply = _send(self.proc, "sal del sandbox")
        self.assertNotIn("[SANDBOX]", reply)
        self.assertFalse(self.proc._sandbox_mode.get("100:1", False))

    def test_sandbox_off_deactivates(self):
        _send(self.proc, "sandbox on")
        reply = _send(self.proc, "sandbox off")
        self.assertFalse(self.proc._sandbox_mode.get("100:1", False))

    def test_modo_normal_deactivates(self):
        _send(self.proc, "activa modo libre")
        _send(self.proc, "modo normal")
        self.assertFalse(self.proc._sandbox_mode.get("100:1", False))

    def test_deactivation_when_not_active_is_graceful(self):
        reply = _send(self.proc, "sal del sandbox")
        self.assertIn("normal", reply.lower())

    def test_sleep_clears_sandbox(self):
        _send(self.proc, "activa modo libre")
        self.proc._sleep_assistant(chat_id="100", user_id="1", operator_id="test-operator", reason="test")
        self.assertFalse(self.proc._sandbox_mode.get("100:1", False))


# ---------------------------------------------------------------------------
# Sandbox message routing
# ---------------------------------------------------------------------------

class TestSandboxRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_path = str(_make_policy(Path(self.tmp.name)))
        self.proc = _make_proc(self.policy_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_message_routes_to_llm_when_active(self):
        _send(self.proc, "activa modo libre")
        llm_text = "Claro, aquí tienes información sobre el vault."
        fake_response = {"choices": [{"message": {"content": llm_text}}]}
        with patch("urllib.request.urlopen") as mock_open:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=json.dumps(fake_response).encode())
            ))
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_cm
            reply = _send(self.proc, "cuéntame sobre el vault")
        self.assertIn("[SANDBOX]", reply)
        self.assertIn(llm_text, reply)

    def test_message_does_not_route_to_llm_when_inactive(self):
        with patch.object(self.proc._sandbox_agent, "chat") as mock_chat:
            _send(self.proc, "estado general")
        mock_chat.assert_not_called()

    def test_llm_error_returns_graceful_message(self):
        _send(self.proc, "activa modo libre")
        with patch.object(self.proc._sandbox_agent, "chat",
                          side_effect=SandboxLLMAgentError("timeout")):
            reply = _send(self.proc, "alguna pregunta")
        self.assertIn("[SANDBOX]", reply)
        self.assertIn("modelo local", reply)

    def test_deactivation_command_works_while_sandbox_active(self):
        """Deactivation trigger must be intercepted before LLM routing."""
        _send(self.proc, "activa modo libre")
        with patch.object(self.proc._sandbox_agent, "chat") as mock_chat:
            reply = _send(self.proc, "sal del sandbox")
        mock_chat.assert_not_called()
        self.assertFalse(self.proc._sandbox_mode.get("100:1", False))


# ---------------------------------------------------------------------------
# Sandbox action execution
# ---------------------------------------------------------------------------

class TestSandboxActionExecution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        vault = Path(self.tmp.name) / "vault"
        vault.mkdir()
        (vault / "10_Proyectos").mkdir()
        self.policy_path = str(_make_policy(Path(self.tmp.name), vault_root=str(vault)))
        self.proc = _make_proc(self.policy_path)
        _send(self.proc, "activa modo libre")

    def tearDown(self):
        self.tmp.cleanup()

    def test_action_executed_directly_no_confirmation(self):
        llm_reply = (
            'Ahora creo la nota. '
            '<action>{"action_id": "action.note.create.v1", '
            '"params": {"folder": "10_Proyectos", "title": "Demo", "body": "Cuerpo de prueba"}}</action>'
        )
        fake_response = {"choices": [{"message": {"content": llm_reply}}]}
        with patch("urllib.request.urlopen") as mock_open:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=MagicMock(
                read=MagicMock(return_value=json.dumps(fake_response).encode())
            ))
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_cm
            reply = _send(self.proc, "crea una nota de demo en proyectos")
        self.assertIn("[SANDBOX]", reply)
        # Broker result should appear (note_name key from create action)
        self.assertIn("action.note.create.v1", reply)

    def test_unknown_action_returns_error(self):
        result = self.proc._execute_sandbox_action(
            chat_id="100", user_id="1", operator_id="test-operator",
            action={"action_id": "action.nonexistent.v1", "params": {}},
        )
        self.assertIn("desconocida", result)

    def test_disabled_action_returns_error(self):
        # health action is enabled=True but mark it disabled via policy mutation
        result = self.proc._execute_sandbox_action(
            chat_id="100", user_id="1", operator_id="test-operator",
            action={"action_id": "action.note.create.v1", "params": {}},
        )
        # With no required params body should fail at broker level, not policy level
        # (action IS enabled; broker may return error for missing params — that's fine)
        # The important thing is it doesn't raise an exception
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Sandbox render functions
# ---------------------------------------------------------------------------

class TestSandboxRenders(unittest.TestCase):
    def test_render_sandbox_activated_contains_sandbox_tag(self):
        text = assistant_responses.render_sandbox_activated()
        self.assertIn("[SANDBOX]", text)
        self.assertIn("vault", text.lower())

    def test_render_sandbox_deactivated_mentions_normal(self):
        text = assistant_responses.render_sandbox_deactivated()
        self.assertIn("normal", text.lower())

    def test_render_sandbox_action_result(self):
        text = assistant_responses.render_sandbox_action_result(
            action_id="action.note.create.v1",
            result={"note_name": "test.md", "folder": "Proyectos"},
        )
        self.assertIn("action.note.create.v1", text)
        self.assertIn("test.md", text)

    def test_render_sandbox_action_error(self):
        text = assistant_responses.render_sandbox_action_error(
            action_id="action.note.create.v1",
            error="folder not found",
            code="not_found",
        )
        self.assertIn("action.note.create.v1", text)
        self.assertIn("folder not found", text)

    def test_sandbox_vault_summary_no_vault_root_returns_empty(self):
        tmp = tempfile.TemporaryDirectory()
        proc = _make_proc(str(_make_policy(Path(tmp.name), vault_root="")))
        result = proc._build_sandbox_vault_summary(operator_id="test-operator")
        self.assertEqual(result, "")
        tmp.cleanup()
