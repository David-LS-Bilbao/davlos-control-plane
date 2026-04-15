from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import unicodedata

import assistant_responses
from assistant_session import AssistantSessionStore
from audit import AuditLogger
from broker import RestrictedOperatorBroker
import cli as broker_cli
from intent_router import IntentRouter
from llm_adapter import LLMAdapter
from models import BrokerRequest, BrokerResult
from policy import PolicyError, PolicyStore

# list_promotable_notes is a read-only operation for /draft_promote listing.
# The bridge lives in scripts/agents/openclaw/ (one level up from this module).
_DRAFT_BRIDGE_DIR = Path(__file__).resolve().parent.parent
if str(_DRAFT_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_DRAFT_BRIDGE_DIR))
from vault_draft_promote_bridge import list_promotable_notes  # noqa: E402
from vault_report_promote_bridge import list_reportable_notes  # noqa: E402
from obsidian_intent_resolver import ResolveResult, get_note_status, resolve_note  # noqa: E402
from vault_artifact_reader import read_pending_artifacts  # noqa: E402
from vault_read_chat import (  # noqa: E402
    list_last_n as vault_list_last_n,
    search_notes as vault_search_notes,
    summarize_today as vault_summarize_today,
    READ_DIRS as VAULT_READ_DIRS,
)


class TelegramApiError(RuntimeError):
    pass


class RateLimitExceededError(RuntimeError):
    pass


@dataclass
class PendingConfirmation:
    intent: str
    operator_id: str
    summary: str
    mutation: str
    action_id: str
    params: dict[str, Any]
    reason: str


class TelegramHttpClient:
    def __init__(self, *, api_base_url: str, token: str):
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base_url}/bot{self.token}/{method}"
        raw = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=raw, method="POST")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=35) as response:
            body = response.read().decode("utf-8", "replace")
        parsed = json.loads(body or "{}")
        if not parsed.get("ok", False):
            raise TelegramApiError(f"telegram api error for {method}")
        return parsed

    def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload).get("result", [])

    def send_message(self, *, chat_id: str, text: str) -> None:
        self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )


class TelegramOffsetStore:
    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> int | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        value = payload.get("next_offset")
        return int(value) if value is not None else None

    def save(self, next_offset: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"next_offset": next_offset}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class TelegramRuntimeStatusStore:
    def __init__(self, path: str):
        self.path = Path(path)

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class SimpleRateLimiter:
    def __init__(self, *, window_seconds: int, max_requests: int):
        self.window_seconds = max(1, window_seconds)
        self.max_requests = max(1, max_requests)
        self.events: dict[str, deque[float]] = {}

    def check(self, principal_id: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        bucket = self.events.setdefault(principal_id, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise RateLimitExceededError(
                f"rate limit exceeded: {self.max_requests}/{self.window_seconds}s"
            )
        bucket.append(now)


class TelegramCommandProcessor:
    def __init__(
        self,
        policy_path: str,
        api_client: TelegramHttpClient | None = None,
        llm_adapter: Any | None = None,
    ):
        self.policy_path = policy_path
        self.policy = PolicyStore(policy_path)
        self.broker = RestrictedOperatorBroker(policy_path)
        self.audit = AuditLogger(self.policy.broker.audit_log_path)
        self.logger = logging.getLogger("davlos.telegram_bot")
        self.rate_limiter = SimpleRateLimiter(
            window_seconds=self.policy.telegram.rate_limit_window_seconds,
            max_requests=self.policy.telegram.rate_limit_max_requests,
        )
        token = os.environ.get(self.policy.telegram.bot_token_env, "")
        self.api_client = api_client or TelegramHttpClient(
            api_base_url=self.policy.telegram.api_base_url,
            token=token,
        )
        self.pending_confirmations: dict[str, PendingConfirmation] = {}
        # C — session note memory: last resolved note per chat:user pair
        self._session_last_note: dict[str, str] = {}
        self.session_store = AssistantSessionStore()
        self.assistant_sessions = self.session_store.sessions
        # Policy value is the base; env var overrides if explicitly set.
        _policy_timeout = self.policy.telegram.assistant_idle_timeout_seconds
        _env_timeout = os.environ.get("OPENCLAW_TELEGRAM_ASSISTANT_IDLE_TIMEOUT_SECONDS")
        self.assistant_idle_timeout_seconds = max(
            60,
            int(_env_timeout) if _env_timeout is not None else _policy_timeout,
        )
        self.llm_adapter = llm_adapter or LLMAdapter()
        self.intent_router = IntentRouter(
            local_matcher=self._detect_conversational_intent,
            llm_adapter=self.llm_adapter,
        )

    def process_update(self, update: dict[str, Any]) -> int | None:
        if isinstance(update.get("edited_message"), dict):
            update_id = update.get("update_id")
            return int(update_id) if isinstance(update_id, int) else None
        message = update.get("message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        text = message.get("text")
        update_id = update.get("update_id")
        if not isinstance(text, str) or not text.strip():
            return int(update_id) if isinstance(update_id, int) else None
        chat_id = str(chat.get("id", ""))
        user_id = str(user.get("id", ""))
        principal_key = f"user:{user_id}" if user_id else f"chat:{chat_id}"
        try:
            self.rate_limiter.check(principal_key)
        except RateLimitExceededError as exc:
            reply = "Rate limit activo. Espera unos segundos y reintenta."
            self._audit_channel_event(
                event="telegram_command_rejected_rate_limited",
                command=text.split(" ", 1)[0] if text.startswith("/") else "conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=None,
                ok=False,
                error=str(exc),
            )
            self.api_client.send_message(chat_id=chat_id, text=reply)
            return int(update_id) if isinstance(update_id, int) else None
        reply = self.handle_text(chat_id=chat_id, user_id=user_id, text=text)
        try:
            self.api_client.send_message(chat_id=chat_id, text=reply)
        except Exception as exc:
            self.logger.warning("telegram send_message failed chat_id=%s error=%s", chat_id, exc)
        return int(update_id) if isinstance(update_id, int) else None

    def handle_text(self, *, chat_id: str, user_id: str, text: str) -> str:
        if len(text) > self.policy.telegram.max_command_length:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/oversize",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=None,
                ok=False,
                error="command exceeds max_command_length",
            )
            return "Comando demasiado largo."
        if "\n" in text or "\r" in text:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/multiline",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=None,
                ok=False,
                error="multiline commands are not allowed",
            )
            return "Comando inválido."
        stripped_text = text.strip()
        command, argument_text = self._split_command(stripped_text)
        principal, operator_id = self.policy.resolve_telegram_operator(chat_id=chat_id, user_id=user_id)
        if principal is None or operator_id is None:
            self._audit_channel_event(
                event="telegram_command_rejected_unauthorized_chat",
                command=command,
                chat_id=chat_id,
                user_id=user_id,
                operator_id=None,
                ok=False,
                error="telegram principal is not allowlisted",
            )
            return "Chat no autorizado para este bot."

        if command.startswith("/"):
            return self._handle_command(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                command=command,
                argument_text=argument_text,
            )

        return self._handle_conversation(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            text=stripped_text,
        )

    def _handle_command(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        command: str,
        argument_text: str,
    ) -> str:
        if command in {"/help", "/start"}:
            self._audit_channel_event(
                event="telegram_command_executed",
                command=command,
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=True,
                result={"kind": "help"},
            )
            return assistant_responses.render_help(operator_id)
        if command == "/wake":
            return self._wake_assistant(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if command == "/sleep":
            return self._sleep_assistant(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                reason="manual",
            )

        if command == "/status":
            return self._handle_status(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if command == "/capabilities":
            return self._handle_capabilities(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if command == "/audit_tail":
            return self._handle_audit_tail(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if command == "/execute":
            return self._handle_execute(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                argument_text=argument_text,
            )
        if command == "/inbox_write":
            return self._handle_inbox_write(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                argument_text=argument_text,
            )
        if command == "/draft_promote":
            return self._handle_draft_promote(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                argument_text=argument_text,
            )
        if command == "/report_promote":
            return self._handle_report_promote(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                argument_text=argument_text,
            )

        self._audit_channel_event(
            event="telegram_command_rejected_unknown",
            command=command,
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=False,
            error="unknown command",
        )
        return "Comando no soportado. Usa /help."

    def _handle_conversation(self, *, chat_id: str, user_id: str, operator_id: str, text: str) -> str:
        normalized = self._normalize_text(text)
        if normalized in {"wake", "despierta", "despierta openclaw", "modo asistente"}:
            return self._wake_assistant(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if normalized in {"sleep", "duerme", "duermete", "sal del modo asistente"}:
            return self._sleep_assistant(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                reason="manual",
            )

        session = self._get_active_session(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        pending = self.pending_confirmations.get(pending_key)
        if pending is not None and self._is_confirmation_accept(normalized):
            self.pending_confirmations.pop(pending_key, None)
            self._audit_channel_event(
                event="confirmation_accepted",
                command="conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=True,
                action_id=pending.action_id,
                params={"intent": pending.intent, "summary": pending.summary},
            )
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id=pending.action_id,
                text=self._execute_pending_confirmation(
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    pending=pending,
                ),
                mode="assistant" if session is not None else "conversation",
                intent=pending.intent,
            )
        if pending is not None and self._is_confirmation_reject(normalized):
            self.pending_confirmations.pop(pending_key, None)
            self._audit_channel_event(
                event="confirmation_rejected",
                command="conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=True,
                action_id=pending.action_id,
                params={"intent": pending.intent, "summary": pending.summary},
            )
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id=pending.action_id,
                text="Acción cancelada. No se aplicó ningún cambio.",
                mode="assistant" if session is not None else "conversation",
                intent=pending.intent,
            )
        if pending is not None:
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id=pending.action_id,
                mode="assistant" if session is not None else "conversation",
                intent="pending_confirmation",
                text=(
                "Hay una acción pendiente de confirmación.\n"
                f"{pending.summary}\n"
                "Responde 'si' para ejecutar o 'no' para cancelar."
            )
            )

        route = self.intent_router.route(text=text, assistant_awake=session is not None)
        if route.llm_invoked:
            self._audit_channel_event(
                event="llm_invoked",
                command="assistant",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=True,
                action_id="telegram.command",
                params={"text_preview": text[:120]},
            )
            if route.llm_validated and route.intent is not None:
                self._audit_channel_event(
                    event="llm_output_validated",
                    command="assistant",
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    ok=True,
                    action_id=route.intent["action_id"],
                    params={"intent": route.intent["intent"]},
                )
            elif route.llm_rejected_reason is not None:
                self._audit_channel_event(
                    event="llm_output_rejected",
                    command="assistant",
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    ok=False,
                    action_id="telegram.command",
                    error=route.llm_rejected_reason,
                    params={"text_preview": text[:120]},
                )

        intent = route.intent
        if intent is None:
            self._audit_channel_event(
                event="intent_rejected_unsupported",
                command="assistant" if session is not None else "conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error="unsupported or ambiguous conversational intent",
                params={"text_preview": text[:120]},
            )
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="telegram.command",
                mode="assistant" if session is not None else "conversation",
                intent="unsupported",
                text=(
                    assistant_responses.render_assistant_fallback()
                    if session is not None
                    else assistant_responses.render_conversation_help()
                ),
            )

        self._audit_channel_event(
            event="intent_detected",
            command="assistant" if session is not None else "conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id=intent["action_id"],
            params={"intent": intent["intent"], "text_preview": text[:120]},
        )
        if intent["intent"] == "status":
            if session is not None:
                return self._response(
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    action_id="telegram.command",
                    mode="assistant",
                    intent="status",
                    text=self._render_assistant_status(chat_id=chat_id, user_id=user_id, operator_id=operator_id),
                )
            return self._handle_status(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "capabilities":
            if session is not None:
                return self._response(
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    action_id="telegram.command",
                    mode="assistant",
                    intent="capabilities",
                    text=self._render_assistant_capabilities(
                        chat_id=chat_id,
                        user_id=user_id,
                        operator_id=operator_id,
                    ),
                )
            return self._handle_capabilities(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "audit_tail":
            if session is not None:
                return self._response(
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    action_id="telegram.command",
                    mode="assistant",
                    intent="audit_tail",
                    text=self._render_assistant_audit_tail(
                        chat_id=chat_id,
                        user_id=user_id,
                        operator_id=operator_id,
                    ),
                )
            return self._handle_audit_tail(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "explain_status":
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="telegram.command",
                mode="assistant",
                intent="explain_status",
                text=self._render_assistant_explanation(
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                ),
            )
        if intent["intent"] == "assistant_identity":
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="telegram.command",
                mode="assistant",
                intent="assistant_identity",
                text=self._render_assistant_identity(operator_id=operator_id),
            )
        if intent["intent"] == "suggest_action":
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="telegram.command",
                mode="assistant",
                intent="suggest_action",
                text=self._render_assistant_suggestion(operator_id=operator_id),
            )
        if intent["intent"] == "logs_read":
            return self._execute_conversation_broker_action(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="action.logs.read.v1",
                params=intent["params"],
            )
        if intent["intent"].startswith("obsidian."):
            return self._handle_obsidian_intent(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                intent=intent,
                assistant_awake=session is not None,
            )
        if intent["intent"] == "unsupported":
            self._audit_channel_event(
                event="intent_rejected_unsupported",
                command="assistant" if session is not None else "conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error="llm returned unsupported intent",
                params={"text_preview": text[:120]},
            )
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="telegram.command",
                mode="assistant" if session is not None else "conversation",
                intent="unsupported",
                text=(
                    assistant_responses.render_assistant_fallback()
                    if session is not None
                    else assistant_responses.render_conversation_help()
                ),
            )

        mutation_permission_error = self._check_mutation_permission(
            operator_id=operator_id,
            action_id=intent["action_id"],
        )
        if mutation_permission_error is not None:
            self._audit_channel_event(
                event="intent_rejected_unauthorized",
                command="assistant" if session is not None else "conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                action_id=intent["action_id"],
                error=mutation_permission_error,
                params={"intent": intent["intent"]},
            )
            return self._response(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id=intent["action_id"],
                mode="assistant" if session is not None else "conversation",
                intent=intent["intent"],
                text=f"No puedo proponer esa acción: {mutation_permission_error}",
            )

        pending = PendingConfirmation(
            intent=intent["intent"],
            operator_id=operator_id,
            summary=intent["summary"],
            mutation=intent["mutation"],
            action_id=intent["action_id"],
            params=intent["params"],
            reason=intent["reason"],
        )
        self.pending_confirmations[pending_key] = pending
        self._audit_channel_event(
            event="confirmation_requested",
            command="assistant" if session is not None else "conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id=pending.action_id,
            params={"intent": pending.intent, "summary": pending.summary},
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id=pending.action_id,
            mode="assistant" if session is not None else "conversation",
            intent=pending.intent,
            text=(
            "Acción interpretada:\n"
            f"{pending.summary}\n"
            "Responde 'si' para ejecutar o 'no' para cancelar."
        )
        )

    def _execute_conversation_broker_action(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        action_id: str,
        params: dict[str, Any],
    ) -> str:
        effective = self.policy.get_effective_action_state(action_id)
        if effective is None:
            return "action_id desconocido."
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission=effective.permission,
            command="conversation",
            chat_id=chat_id,
            user_id=user_id,
            action_id=action_id,
        )
        if operator is None:
            return f"Operador no autorizado para {action_id}."
        result = self.broker.execute(BrokerRequest(action_id=action_id, params=params, actor=operator_id))
        self._audit_channel_event(
            event="telegram_action_requested",
            command="conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=result.ok,
            result=result.to_dict(),
            error=result.error,
            code=result.code,
            operator_role=operator.role,
            action_id=action_id,
            params=self._safe_params_for_audit(params),
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id=action_id,
            mode="assistant" if self._has_active_session(chat_id=chat_id, user_id=user_id, operator_id=operator_id) else "conversation",
            intent="logs_read",
            text=self._render_execution_result(result),
        )

    def _execute_pending_confirmation(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        pending: PendingConfirmation,
    ) -> str:
        if pending.operator_id != operator_id:
            return "La confirmación no coincide con el operador actual."
        rc = 1
        if pending.mutation == "set_enabled":
            rc = broker_cli.set_enabled(
                self.policy_path,
                pending.action_id,
                bool(pending.params["enabled"]),
                operator_id,
                operator_id,
                pending.reason,
            )
        elif pending.mutation == "enable_with_ttl":
            rc = broker_cli.enable_with_optional_ttl(
                self.policy_path,
                pending.action_id,
                ttl_minutes=int(pending.params["ttl_minutes"]),
                expires_at=None,
                operator_id=operator_id,
                updated_by=operator_id,
                reason=pending.reason,
            )
        elif pending.mutation == "reset_one_shot":
            rc = broker_cli.reset_one_shot(
                self.policy_path,
                pending.action_id,
                operator_id,
                operator_id,
                pending.reason,
            )
        elif pending.mutation == "inbox_write":
            result = self.broker.execute(
                BrokerRequest(
                    action_id="action.inbox.write.v1",
                    params=pending.params,
                    actor=pending.operator_id,
                )
            )
            body = pending.params.get("capture_body") or ""
            audit_p = {
                "run_id": pending.params.get("run_id"),
                "capture_title": pending.params.get("capture_title"),
                "body_bytes": len(body.encode("utf-8")),
                "source_refs_count": len(pending.params.get("source_refs") or []),
            }
            self._audit_channel_event(
                event="action_executed" if result.ok else "action_failed",
                command="/inbox_write",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=result.ok,
                action_id="action.inbox.write.v1",
                params=audit_p,
                result=result.to_dict() if result.ok else None,
                error=result.error,
                code=result.code,
            )
            if result.ok:
                note_name = result.result.get("note_name", "?")
                # B — post-action suggestion: capture → suggest draft promote
                return (
                    f"Captura guardada.\nnota: {note_name}\n"
                    f"→ Cuando quieras, usa 'promueve {note_name} a draft'."
                )
            return f"Error guardando captura.\ncode={result.code}\nerror={result.error}"
        elif pending.mutation == "draft_promote":
            result = self.broker.execute(
                BrokerRequest(
                    action_id="action.draft.promote.v1",
                    params=pending.params,
                    actor=pending.operator_id,
                )
            )
            audit_p = {
                "note_name": pending.params.get("note_name"),
            }
            self._audit_channel_event(
                event="action_executed" if result.ok else "action_failed",
                command="/draft_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=result.ok,
                action_id="action.draft.promote.v1",
                params=audit_p,
                result=result.to_dict() if result.ok else None,
                error=result.error,
                code=result.code,
            )
            if result.ok:
                promoted_note = result.result.get("note_name", "?")
                promoted_title = result.result.get("title", "?")
                # B — post-action suggestion: draft → suggest report when pipeline is free
                return (
                    f"Nota promovida a draft.\n"
                    f"nota: {promoted_note}\n"
                    f"título: {promoted_title}\n"
                    f"staging: STAGED_INPUT.md creado\n"
                    "→ Cuando el pipeline consuma STAGED_INPUT.md, usa 'promueve a report'."
                )
            return self._render_promote_error(
                note_name=pending.params.get("note_name", "nota"),
                code=result.code or "unknown",
                target="draft",
            )
        elif pending.mutation == "report_promote":
            result = self.broker.execute(
                BrokerRequest(
                    action_id="action.report.promote.v1",
                    params=pending.params,
                    actor=pending.operator_id,
                )
            )
            audit_p = {
                "note_name": pending.params.get("note_name"),
            }
            self._audit_channel_event(
                event="action_executed" if result.ok else "action_failed",
                command="/report_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=result.ok,
                action_id="action.report.promote.v1",
                params=audit_p,
                result=result.to_dict() if result.ok else None,
                error=result.error,
                code=result.code,
            )
            if result.ok:
                promoted_note = result.result.get("note_name", "?")
                promoted_title = result.result.get("title", "?")
                # B — post-action suggestion: report → pipeline follow-up
                return (
                    f"Nota promovida a report.\n"
                    f"nota: {promoted_note}\n"
                    f"título: {promoted_title}\n"
                    f"report: REPORT_INPUT.md creado\n"
                    "→ El pipeline procesará REPORT_INPUT.md. Usa 'qué artefactos pendientes hay' para seguimiento."
                )
            return self._render_promote_error(
                note_name=pending.params.get("note_name", "nota"),
                code=result.code or "unknown",
                target="report",
            )
        else:
            return "Intención pendiente no soportada."
        self._audit_channel_event(
            event="action_executed" if rc == 0 else "action_failed",
            command="conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=rc == 0,
            action_id=pending.action_id,
            params={"intent": pending.intent, "summary": pending.summary},
        )
        return assistant_responses.render_mutation_result(
            ok=rc == 0,
            summary=pending.summary,
            action_id=pending.action_id,
        )

    def _handle_status(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="policy.read",
            command="/status",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "Operador no autorizado para consultar estado."
        states = self.policy.list_effective_action_states()
        summary = {"enabled": 0, "disabled": 0, "expired": 0, "consumed": 0}
        for state in states:
            summary[state.status] = summary.get(state.status, 0) + 1
        message = (
            f"operator={operator.operator_id}\n"
            f"actions_total={len(states)}\n"
            f"enabled={summary.get('enabled', 0)} disabled={summary.get('disabled', 0)}\n"
            f"expired={summary.get('expired', 0)} consumed={summary.get('consumed', 0)}"
        )
        self._audit_channel_event(
            event="telegram_command_executed",
            command="/status",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            result={"actions_total": len(states)},
            operator_role=operator.role,
        )
        return message

    def _handle_capabilities(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="policy.read",
            command="/capabilities",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "Operador no autorizado para consultar capacidades."
        rows = []
        for state in self.policy.list_effective_action_states():
            can_execute = self._can_operator(operator_id, state.permission)
            rows.append(
                f"{state.action_id} status={state.status} mode={state.mode} exec={'yes' if can_execute else 'no'}"
            )
        message = self._limit_message("\n".join(rows) if rows else "No hay acciones configuradas.")
        self._audit_channel_event(
            event="telegram_command_executed",
            command="/capabilities",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            result={"count": len(rows)},
            operator_role=operator.role,
        )
        return message

    def _handle_audit_tail(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.audit",
            command="/audit_tail",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "Operador no autorizado para consultar auditoría."
        audit_path = Path(self.policy.broker.audit_log_path)
        if not audit_path.exists():
            return "No hay eventos de auditoría todavía."
        lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows = []
        for line in lines[-self.policy.telegram.audit_tail_lines :]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(
                f"{payload.get('ts','?')} {payload.get('event','?')} action={payload.get('action_id','-')} ok={payload.get('ok')}"
            )
        self._audit_channel_event(
            event="telegram_command_executed",
            command="/audit_tail",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            result={"lines": len(rows)},
            operator_role=operator.role,
        )
        return self._limit_message("\n".join(rows) if rows else "No hay eventos legibles.")

    def _handle_execute(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        argument_text: str,
    ) -> str:
        try:
            action_id, params = self._parse_execute_arguments(argument_text)
        except PolicyError as exc:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/execute",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=str(exc),
            )
            return f"Parámetros inválidos: {exc}"

        effective = self.policy.get_effective_action_state(action_id)
        if effective is None:
            self._audit_channel_event(
                event="telegram_command_rejected_unknown_action",
                command="/execute",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error="unknown action_id",
                action_id=action_id,
            )
            return "action_id desconocido."

        operator = self._authorize_operator(
            operator_id=operator_id,
            permission=effective.permission,
            command="/execute",
            chat_id=chat_id,
            user_id=user_id,
            action_id=action_id,
        )
        if operator is None:
            return f"Operador no autorizado para {action_id}."

        result = self.broker.execute(BrokerRequest(action_id=action_id, params=params, actor=operator_id))
        self._audit_channel_event(
            event="telegram_action_requested",
            command="/execute",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=result.ok,
            result=result.to_dict(),
            error=result.error,
            code=result.code,
            operator_role=operator.role,
            action_id=action_id,
            params=self._safe_params_for_audit(params),
        )
        return self._render_execution_result(result)

    def _authorize_operator(
        self,
        *,
        operator_id: str,
        permission: str,
        command: str,
        chat_id: str,
        user_id: str,
        action_id: str = "telegram.command",
    ):
        try:
            return self.policy.authorize_operator(operator_id, permission)
        except PolicyError as exc:
            self._audit_channel_event(
                event="telegram_command_rejected_operator_not_authorized",
                command=command,
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=str(exc),
                action_id=action_id,
            )
            return None

    def _can_operator(self, operator_id: str, permission: str) -> bool:
        try:
            self.policy.authorize_operator(operator_id, permission)
            return True
        except PolicyError:
            return False

    @staticmethod
    def _session_key(*, chat_id: str, user_id: str) -> str:
        return AssistantSessionStore.session_key(chat_id=chat_id, user_id=user_id)

    @staticmethod
    def _pending_key(*, chat_id: str, user_id: str) -> str:
        return f"{chat_id}:{user_id}"

    # C — note alias helpers
    _NOTE_ALIASES: frozenset[str] = frozenset({"esa", "la misma", "esa nota", "misma nota"})

    def _save_session_note(self, *, chat_id: str, user_id: str, note_name: str) -> None:
        """Remember the last resolved note for this session."""
        self._session_last_note[self._pending_key(chat_id=chat_id, user_id=user_id)] = note_name

    def _resolve_note_alias(self, *, note_ref: str, chat_id: str, user_id: str) -> str:
        """If note_ref is a session alias, substitute stored note name."""
        if note_ref.strip().lower() in self._NOTE_ALIASES:
            stored = self._session_last_note.get(self._pending_key(chat_id=chat_id, user_id=user_id))
            if stored:
                return stored
        return note_ref

    @staticmethod
    def _now_monotonic() -> float:
        return AssistantSessionStore.now_monotonic()

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = "".join(ch if not unicodedata.category(ch).startswith("P") else " " for ch in normalized)
        return " ".join(normalized.lower().strip().split())

    @staticmethod
    def _is_confirmation_accept(normalized: str) -> bool:
        return normalized in {"si", "sí", "confirmar", "confirmo", "ok", "dale"}

    @staticmethod
    def _is_confirmation_reject(normalized: str) -> bool:
        return normalized in {"no", "cancelar", "cancela", "rechazar"}

    def _detect_conversational_intent(self, text: str, *, assistant_awake: bool) -> dict[str, Any] | None:
        normalized = self._normalize_text(text)
        if normalized in {"estado", "estado general", "como va", "como va openclaw", "salud general"}:
            return {"intent": "status", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "como estamos",
            "que tal estamos",
            "estado del sistema",
            "como esta todo",
            "dame un resumen del estado",
        }:
            return {"intent": "status", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "quien eres",
            "quien eres tu",
            "que eres",
            "presentate",
        }:
            return {"intent": "assistant_identity", "action_id": "telegram.command", "params": {}}
        if normalized in {
            "capacidades",
            "capacidades activas",
            "que capacidades hay",
            "que capacidades estan activas",
            "capabilities",
        }:
            return {"intent": "capabilities", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "que puedes hacer",
            "que tienes activo",
            "que esta habilitado",
            "que capacidades puedo usar",
        }:
            return {"intent": "capabilities", "action_id": "telegram.command", "params": {}}
        if normalized in {"auditoria", "auditoria reciente", "audit", "audit tail", "ultimos eventos"}:
            return {"intent": "audit_tail", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "que ha pasado",
            "que paso recientemente",
            "ultimos cambios",
            "que hiciste",
        }:
            return {"intent": "audit_tail", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "explica el estado",
            "explicame el estado",
            "resume el estado",
            "por que esta asi",
        }:
            return {"intent": "explain_status", "action_id": "telegram.command", "params": {}}
        if assistant_awake and self._looks_like_conceptual_explain_status(normalized):
            return {"intent": "explain_status", "action_id": "telegram.command", "params": {}}
        if assistant_awake and normalized in {
            "que propones",
            "que recomiendas",
            "propon una accion",
            "propon acciones",
            "que harias",
        }:
            return {"intent": "suggest_action", "action_id": "telegram.command", "params": {}}
        if assistant_awake and self._looks_like_prudent_suggestion_request(normalized):
            return {"intent": "suggest_action", "action_id": "telegram.command", "params": {}}

        logs_intent = self._match_logs_intent(normalized)
        if logs_intent is not None:
            return logs_intent

        ttl_intent = self._match_enable_ttl_intent(normalized)
        if ttl_intent is not None:
            return ttl_intent

        set_enabled_intent = self._match_set_enabled_intent(normalized)
        if set_enabled_intent is not None:
            return set_enabled_intent

        reset_intent = self._match_reset_one_shot_intent(normalized)
        if reset_intent is not None:
            return reset_intent

        obsidian_intent = self._match_obsidian_intent(normalized=normalized, original_text=text)
        if obsidian_intent is not None:
            return obsidian_intent

        return None

    @staticmethod
    def _looks_like_conceptual_explain_status(normalized: str) -> bool:
        if "que significa" not in normalized and "explicame" not in normalized:
            return False
        return any(token in normalized for token in {"enabled", "disabled", "deshabilitada", "expirada", "expired", "consumida", "one shot"})

    @staticmethod
    def _looks_like_prudent_suggestion_request(normalized: str) -> bool:
        suggestion_markers = {"que propones", "que recomiendas", "mejorar la operacion", "sin tocar nada sensible", "sin tocar nada", "prudente"}
        return any(marker in normalized for marker in suggestion_markers)

    def _match_logs_intent(self, normalized: str) -> dict[str, Any] | None:
        if "log" not in normalized:
            return None
        stream_id = "openclaw_runtime"
        if "audit" in normalized or "auditoria" in normalized:
            stream_id = "restricted_operator_audit"
        tail_lines = 20
        for token in normalized.split():
            if token.isdigit():
                tail_lines = int(token)
                break
        return {
            "intent": "logs_read",
            "action_id": "action.logs.read.v1",
            "params": {"stream_id": stream_id, "tail_lines": tail_lines},
        }

    def _match_set_enabled_intent(self, normalized: str) -> dict[str, Any] | None:
        action_id = self._extract_action_id(normalized)
        if action_id is None:
            return None
        if normalized.startswith("habilita ") or normalized.startswith("activar ") or normalized.startswith("activa "):
            return {
                "intent": "enable_capability",
                "action_id": action_id,
                "mutation": "set_enabled",
                "params": {"enabled": True},
                "reason": "telegram_conversational_enable",
                "summary": f"Habilitar {action_id}",
            }
        if normalized.startswith("deshabilita ") or normalized.startswith("desactiva "):
            return {
                "intent": "disable_capability",
                "action_id": action_id,
                "mutation": "set_enabled",
                "params": {"enabled": False},
                "reason": "telegram_conversational_disable",
                "summary": f"Deshabilitar {action_id}",
            }
        return None

    def _match_enable_ttl_intent(self, normalized: str) -> dict[str, Any] | None:
        if not (normalized.startswith("habilita ") or normalized.startswith("activa ")):
            return None
        action_id = self._extract_action_id(normalized)
        if action_id is None:
            return None
        ttl_minutes: int | None = None
        tokens = normalized.split()
        for index, token in enumerate(tokens):
            if token.isdigit():
                next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
                if next_token.startswith("min"):
                    ttl_minutes = int(token)
                    break
        if ttl_minutes is None:
            return None
        return {
            "intent": "enable_capability_with_ttl",
            "action_id": action_id,
            "mutation": "enable_with_ttl",
            "params": {"ttl_minutes": ttl_minutes},
            "reason": "telegram_conversational_enable_ttl",
            "summary": f"Habilitar {action_id} durante {ttl_minutes} minutos",
        }

    def _match_reset_one_shot_intent(self, normalized: str) -> dict[str, Any] | None:
        if "reset" not in normalized and "resetea" not in normalized:
            return None
        if "one shot" not in normalized and "one-shot" not in normalized:
            return None
        action_id = self._extract_action_id(normalized)
        if action_id is None:
            return None
        return {
            "intent": "reset_one_shot",
            "action_id": action_id,
            "mutation": "reset_one_shot",
            "params": {},
            "reason": "telegram_conversational_reset_one_shot",
            "summary": f"Resetear one-shot de {action_id}",
        }

    @staticmethod
    def _extract_action_id(normalized: str) -> str | None:
        aliases = {
            "dropzone": "action.dropzone.write.v1",
            "inbox": "action.inbox.write.v1",
            "draft_promote": "action.draft.promote.v1",
            "report_promote": "action.report.promote.v1",
            "webhook": "action.webhook.trigger.v1",
            "restart": "action.openclaw.restart.v1",
        }
        for token in normalized.replace(",", " ").split():
            if token.startswith("action.") and token.endswith(".v1"):
                return token
            if token in aliases:
                return aliases[token]
        return None

    def _handle_inbox_write(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        argument_text: str,
    ) -> str:
        try:
            params = self._parse_inbox_write_arguments(argument_text)
        except PolicyError as exc:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/inbox_write",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=str(exc),
            )
            return f"Parámetros inválidos: {exc}"

        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.write",
            command="/inbox_write",
            chat_id=chat_id,
            user_id=user_id,
            action_id="action.inbox.write.v1",
        )
        if operator is None:
            return "Operador no autorizado para action.inbox.write.v1."

        effective = self.policy.get_effective_action_state("action.inbox.write.v1")
        if effective is None or not effective.effective_allowed:
            status = effective.status if effective is not None else "unknown"
            self._audit_channel_event(
                event="telegram_command_rejected_action_not_allowed",
                command="/inbox_write",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=f"action not allowed: {status}",
                action_id="action.inbox.write.v1",
            )
            return f"La acción inbox.write no está habilitada (status={status})."

        body = params["capture_body"]
        body_bytes = len(body.encode("utf-8"))
        summary = (
            f"inbox.write | run_id={params['run_id']} | "
            f"title={params['capture_title']} | body={body_bytes} B"
        )
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        pending = PendingConfirmation(
            intent="inbox_write",
            operator_id=operator_id,
            summary=summary,
            mutation="inbox_write",
            action_id="action.inbox.write.v1",
            params=params,
            reason="telegram_inbox_write",
        )
        self.pending_confirmations[pending_key] = pending
        session = self._get_active_session(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        self._audit_channel_event(
            event="confirmation_requested",
            command="/inbox_write",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id="action.inbox.write.v1",
            params={"intent": "inbox_write", "summary": summary},
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id="action.inbox.write.v1",
            mode="assistant" if session is not None else "conversation",
            intent="inbox_write",
            text=(
                f"Acción interpretada:\n{summary}\n"
                "Responde 'si' para ejecutar o 'no' para cancelar."
            ),
        )

    @staticmethod
    def _parse_inbox_write_arguments(argument_text: str) -> dict[str, Any]:
        if "::" not in argument_text:
            raise PolicyError("uso: /inbox_write run_id=<id> title=<titulo> :: <cuerpo>")
        header_part, _, body_part = argument_text.partition("::")
        capture_body = body_part.strip()
        if not capture_body:
            raise PolicyError("capture_body no puede estar vacío")
        tokens = header_part.strip().split()
        if not tokens:
            raise PolicyError("run_id y title son requeridos")
        raw: dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise PolicyError("parámetros de cabecera deben ser k=v")
            key, value = token.split("=", 1)
            key = key.strip()
            if not key:
                raise PolicyError("clave vacía en parámetros")
            import urllib.parse as _urlparse
            raw[key] = _urlparse.unquote_plus(value.strip())
        run_id = raw.get("run_id", "").strip()
        if not run_id:
            raise PolicyError("run_id requerido")
        capture_title = raw.get("title", "").strip()
        if not capture_title:
            raise PolicyError("title requerido")
        source_refs_raw = raw.get("source_refs", "").strip()
        source_refs: list[str] | None = (
            [r.strip() for r in source_refs_raw.split(",") if r.strip()]
            if source_refs_raw
            else None
        )
        return {
            "run_id": run_id,
            "capture_title": capture_title,
            "capture_body": capture_body,
            "source_refs": source_refs,
        }

    def _handle_draft_promote(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        argument_text: str,
    ) -> str:
        # --- no arguments → list promotable notes ---
        if not argument_text.strip():
            vault_root = self.policy.vault_inbox.vault_root
            if not vault_root:
                return "vault_inbox.vault_root no configurado."
            try:
                notes = list_promotable_notes(vault_root=vault_root, max_results=10)
            except Exception as exc:
                self._audit_channel_event(
                    event="telegram_command_rejected_error",
                    command="/draft_promote",
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    ok=False,
                    error=str(exc),
                    action_id="action.draft.promote.v1",
                )
                return f"Error listando notas: {exc}"
            if not notes:
                return "No hay notas promotables (pending_triage) en inbox."
            rows = [f"- {n['note_name']}  run_id={n['run_id']}  {n['created_at_utc']}" for n in notes]
            return (
                "Notas promotables:\n"
                + "\n".join(rows)
                + "\n\nUsa: /draft_promote note=<nombre_archivo>"
            )

        # --- with arguments → parse and confirm ---
        try:
            params = self._parse_draft_promote_arguments(argument_text)
        except PolicyError as exc:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/draft_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=str(exc),
            )
            return f"Parámetros inválidos: {exc}"

        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.write",
            command="/draft_promote",
            chat_id=chat_id,
            user_id=user_id,
            action_id="action.draft.promote.v1",
        )
        if operator is None:
            return "Operador no autorizado para action.draft.promote.v1."

        effective = self.policy.get_effective_action_state("action.draft.promote.v1")
        if effective is None or not effective.effective_allowed:
            status = effective.status if effective is not None else "unknown"
            self._audit_channel_event(
                event="telegram_command_rejected_action_not_allowed",
                command="/draft_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=f"action not allowed: {status}",
                action_id="action.draft.promote.v1",
            )
            return f"La acción draft.promote no está habilitada (status={status})."

        note_name = params["note_name"]
        summary = f"draft.promote | note={note_name}"
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        pending = PendingConfirmation(
            intent="draft_promote",
            operator_id=operator_id,
            summary=summary,
            mutation="draft_promote",
            action_id="action.draft.promote.v1",
            params=params,
            reason="telegram_draft_promote",
        )
        self.pending_confirmations[pending_key] = pending
        session = self._get_active_session(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        self._audit_channel_event(
            event="confirmation_requested",
            command="/draft_promote",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id="action.draft.promote.v1",
            params={"intent": "draft_promote", "summary": summary},
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id="action.draft.promote.v1",
            mode="assistant" if session is not None else "conversation",
            intent="draft_promote",
            text=(
                f"Acción interpretada:\n{summary}\n"
                "Responde 'si' para ejecutar o 'no' para cancelar."
            ),
        )

    @staticmethod
    def _parse_draft_promote_arguments(argument_text: str) -> dict[str, Any]:
        tokens = argument_text.strip().split()
        if not tokens:
            raise PolicyError("uso: /draft_promote note=<nombre_archivo>")
        raw: dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise PolicyError("parámetros deben ser k=v")
            key, value = token.split("=", 1)
            key = key.strip()
            if not key:
                raise PolicyError("clave vacía en parámetros")
            raw[key] = value.strip()
        note_name = raw.get("note", "").strip()
        if not note_name:
            raise PolicyError("note requerido: /draft_promote note=<nombre_archivo>")
        if len(note_name) > 256:
            raise PolicyError("note_name demasiado largo")
        return {"note_name": note_name}

    def _handle_report_promote(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        argument_text: str,
    ) -> str:
        # --- no arguments → list reportable notes ---
        if not argument_text.strip():
            vault_root = self.policy.vault_inbox.vault_root
            if not vault_root:
                return "vault_inbox.vault_root no configurado."
            try:
                notes = list_reportable_notes(vault_root=vault_root, max_results=10)
            except Exception as exc:
                self._audit_channel_event(
                    event="telegram_command_rejected_error",
                    command="/report_promote",
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    ok=False,
                    error=str(exc),
                    action_id="action.report.promote.v1",
                )
                return f"Error listando notas: {exc}"
            if not notes:
                return "No hay notas en estado promoted_to_draft para reportar."
            rows = [f"- {n['note_name']}  run_id={n['run_id']}  {n['created_at_utc']}" for n in notes]
            return (
                "Notas listas para report:\n"
                + "\n".join(rows)
                + "\n\nUsa: /report_promote note=<nombre_archivo>"
            )

        # --- with arguments → parse and confirm ---
        try:
            params = self._parse_report_promote_arguments(argument_text)
        except PolicyError as exc:
            self._audit_channel_event(
                event="telegram_command_rejected_invalid_params",
                command="/report_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=str(exc),
            )
            return f"Parámetros inválidos: {exc}"

        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.write",
            command="/report_promote",
            chat_id=chat_id,
            user_id=user_id,
            action_id="action.report.promote.v1",
        )
        if operator is None:
            return "Operador no autorizado para action.report.promote.v1."

        effective = self.policy.get_effective_action_state("action.report.promote.v1")
        if effective is None or not effective.effective_allowed:
            status = effective.status if effective is not None else "unknown"
            self._audit_channel_event(
                event="telegram_command_rejected_action_not_allowed",
                command="/report_promote",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error=f"action not allowed: {status}",
                action_id="action.report.promote.v1",
            )
            return f"La acción report.promote no está habilitada (status={status})."

        note_name = params["note_name"]
        summary = f"report.promote | note={note_name}"
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        pending = PendingConfirmation(
            intent="report_promote",
            operator_id=operator_id,
            summary=summary,
            mutation="report_promote",
            action_id="action.report.promote.v1",
            params=params,
            reason="telegram_report_promote",
        )
        self.pending_confirmations[pending_key] = pending
        session = self._get_active_session(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        self._audit_channel_event(
            event="confirmation_requested",
            command="/report_promote",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id="action.report.promote.v1",
            params={"intent": "report_promote", "summary": summary},
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id="action.report.promote.v1",
            mode="assistant" if session is not None else "conversation",
            intent="report_promote",
            text=(
                f"Acción interpretada:\n{summary}\n"
                "Responde 'si' para ejecutar o 'no' para cancelar."
            ),
        )

    @staticmethod
    def _parse_report_promote_arguments(argument_text: str) -> dict[str, Any]:
        tokens = argument_text.strip().split()
        if not tokens:
            raise PolicyError("uso: /report_promote note=<nombre_archivo>")
        raw: dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise PolicyError("parámetros deben ser k=v")
            key, value = token.split("=", 1)
            key = key.strip()
            if not key:
                raise PolicyError("clave vacía en parámetros")
            raw[key] = value.strip()
        note_name = raw.get("note", "").strip()
        if not note_name:
            raise PolicyError("note requerido: /report_promote note=<nombre_archivo>")
        if len(note_name) > 256:
            raise PolicyError("note_name demasiado largo")
        return {"note_name": note_name}

    # -----------------------------------------------------------------------
    # Phase 4 — Obsidian conversational layer
    # -----------------------------------------------------------------------

    # Trigger sets for list intents
    _OBS_LIST_PENDING_TRIGGERS = frozenset({
        "que tengo pendiente", "notas pendientes", "listar pendientes",
        "que hay en inbox", "inbox pendiente", "notas en inbox",
        "que esta pendiente", "listas para draft", "notas para draft",
        "que esta listo para draft", "pending triage", "que hay pendiente",
        "mostrar pendientes", "muestrame notas pendientes",
    })
    _OBS_LIST_REPORT_TRIGGERS = frozenset({
        "listas para report", "notas para report", "listar report",
        "que esta listo para report", "promoted to draft",
        "notas en draft", "que esta en draft",
        "mostrar report", "muestrame notas para report",
    })
    # Prefixes that signal a capture intent (checked against original_text.lower())
    _OBS_CAPTURE_PREFIXES: tuple[str, ...] = (
        "guarda esta idea:",
        "guarda esta idea",
        "anota esto:",
        "anota esto",
        "guarda una nota:",
        "guarda una nota",
        "captura:",
        "guarda en obsidian:",
        "guarda en obsidian",
        "guarda nota:",
        "guarda nota",
    )
    # Prefixes that signal a status query
    _OBS_STATUS_PREFIXES: tuple[str, ...] = (
        "que estado tiene ",
        "estado de la nota ",
        "busca la nota ",
        "estado nota ",
        "dime el estado de ",
        "busca nota ",
        "estado de ",
    )
    # Phase 5 — Vault Read Chat trigger sets
    _OBS_LAST_N_PREFIXES: tuple[str, ...] = (
        "muestrame las ultimas ",
        "muestra las ultimas ",
        "dame las ultimas ",
        "las ultimas ",
        "ultimas ",
    )
    _OBS_SEARCH_PREFIXES_P5: tuple[str, ...] = (
        "busca ",
        "buscar ",
        "encuentra ",
        "encontrar ",
    )
    _OBS_SUMMARY_TODAY_TRIGGERS = frozenset({
        "resumeme lo guardado hoy",
        "resume lo guardado hoy",
        "que guarde hoy",
        "que he guardado hoy",
        "resumen de hoy",
        "notas de hoy",
        "guardado hoy",
        "que capture hoy",
        "que cree hoy",
    })
    # Phase 6 — Operational Hygiene trigger sets
    _OBS_HELP_TRIGGERS = frozenset({
        "que puedes hacer con obsidian",
        "ayuda obsidian",
        "ayuda vault",
        "que puedo hacer con obsidian",
        "que puedo hacer con el vault",
        "que puedes hacer con el vault",
        "help obsidian",
        "help vault",
        "obsidian help",
        "vault help",
        "comandos obsidian",
        "comandos vault",
    })
    _OBS_PENDING_ARTIFACTS_TRIGGERS = frozenset({
        "que artefactos pendientes hay",
        "hay artefactos pendientes",
        "artefactos pendientes",
        "staged input pendiente",
        "report input pendiente",
        "que hay en cola",
        "que esta en cola",
        "pipeline bloqueado",
        "hay algo en cola",
        "que bloquea el pipeline",
    })
    _OBS_WHAT_BLOCKS_PREFIXES: tuple[str, ...] = (
        "que bloquea ",
        "por que no puedo promover ",
        "por que no se puede promover ",
        "que impide promover ",
        "que le pasa a ",
    )

    def _match_obsidian_intent(
        self, *, normalized: str, original_text: str
    ) -> dict[str, Any] | None:
        """Return an obsidian.* intent dict or None if no match."""

        # --- Phase 6: obsidian help ---
        if normalized in self._OBS_HELP_TRIGGERS:
            return {"intent": "obsidian.help", "action_id": "telegram.command", "params": {}}

        # --- Phase 6: pending pipeline artifacts (read-only) ---
        if normalized in self._OBS_PENDING_ARTIFACTS_TRIGGERS:
            return {"intent": "obsidian.pending_artifacts", "action_id": "telegram.command", "params": {}}

        # --- Phase 6: what blocks a note ---
        for prefix in self._OBS_WHAT_BLOCKS_PREFIXES:
            if normalized.startswith(prefix):
                ref = normalized[len(prefix):].strip()
                if ref:
                    return {
                        "intent": "obsidian.what_blocks",
                        "action_id": "telegram.command",
                        "params": {"note_ref": ref},
                    }

        # --- list pending (pending_triage) ---
        if normalized in self._OBS_LIST_PENDING_TRIGGERS:
            return {"intent": "obsidian.list_pending", "action_id": "telegram.command", "params": {}}

        # --- list report-ready (promoted_to_draft) ---
        if normalized in self._OBS_LIST_REPORT_TRIGGERS:
            return {"intent": "obsidian.list_report_ready", "action_id": "telegram.command", "params": {}}

        # --- note status query ---
        for prefix in self._OBS_STATUS_PREFIXES:
            if normalized.startswith(prefix):
                ref = normalized[len(prefix):].strip()
                if ref:
                    return {
                        "intent": "obsidian.show_note_status",
                        "action_id": "telegram.command",
                        "params": {"note_ref": ref},
                    }

        # --- promote to draft ---
        if ("draft" in normalized and not "report" in normalized and
                any(kw in normalized for kw in ("promueve", "promover", "promociona", "pasa a draft"))):
            ref = self._extract_obsidian_note_ref(normalized, target="draft")
            if ref is not None:
                return {
                    "intent": "obsidian.promote_to_draft",
                    "action_id": "action.draft.promote.v1",
                    "params": {"note_ref": ref},
                }

        # --- promote to report ---
        if ("report" in normalized and
                any(kw in normalized for kw in ("promueve", "promover", "promociona", "pasa a report"))):
            ref = self._extract_obsidian_note_ref(normalized, target="report")
            if ref is not None:
                return {
                    "intent": "obsidian.promote_to_report",
                    "action_id": "action.report.promote.v1",
                    "params": {"note_ref": ref},
                }

        # --- capture (require :: separator for title/body split) ---
        orig_lower = original_text.lower().strip()
        for prefix in self._OBS_CAPTURE_PREFIXES:
            if orig_lower.startswith(prefix):
                remainder = original_text[len(prefix):].strip()
                if "::" in remainder:
                    title, _, body = remainder.partition("::")
                    title = title.strip()
                    body = body.strip()
                    if title and body:
                        return {
                            "intent": "obsidian.capture",
                            "action_id": "action.inbox.write.v1",
                            "params": {"title": title, "body": body},
                        }
                # Trigger detected but format incomplete → ask for clarification
                return {
                    "intent": "obsidian.capture_clarify",
                    "action_id": "telegram.command",
                    "params": {},
                }

        # --- Phase 5: last N notes ---
        for prefix in self._OBS_LAST_N_PREFIXES:
            if normalized.startswith(prefix):
                n = self._extract_number_from_text(normalized, default=5, max_val=10)
                return {
                    "intent": "obsidian.list_last_n",
                    "action_id": "telegram.command",
                    "params": {"n": n},
                }

        # --- Phase 5: text search (checked AFTER status prefixes above) ---
        for prefix in self._OBS_SEARCH_PREFIXES_P5:
            if normalized.startswith(prefix):
                query = normalized[len(prefix):].strip()
                if len(query) >= 2:
                    return {
                        "intent": "obsidian.search_text",
                        "action_id": "telegram.command",
                        "params": {"query": query},
                    }

        # --- Phase 5: summary today ---
        if normalized in self._OBS_SUMMARY_TODAY_TRIGGERS:
            return {"intent": "obsidian.summary_today", "action_id": "telegram.command", "params": {}}

        return None

    @staticmethod
    def _extract_obsidian_note_ref(normalized: str, *, target: str) -> str | None:
        """Extract the note reference token(s) from a promote phrase.

        Strips known command words and the target keyword; returns the remainder
        as the note_ref string, or None if nothing useful remains.
        """
        stop = {target, "a", "la", "nota", "promueve", "promover", "pasa",
                "al", "hacia", "promociona", "de", "el", "draft", "report", "hacia"}
        tokens = [t for t in normalized.split() if t not in stop]
        if not tokens:
            return None
        return " ".join(tokens)

    @staticmethod
    def _extract_number_from_text(text: str, *, default: int, max_val: int) -> int:
        """Return first integer found in text, clamped to [1, max_val]."""
        import re as _re
        m = _re.search(r"\b(\d+)\b", text)
        if m:
            try:
                return max(1, min(int(m.group(1)), max_val))
            except ValueError:
                pass
        return default

    def _handle_obsidian_intent(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        intent: dict[str, Any],
        assistant_awake: bool,
    ) -> str:
        mode = "assistant" if assistant_awake else "conversation"
        sub = intent["intent"]

        # --- Phase 6: obsidian help ---
        if sub == "obsidian.help":
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub, text=assistant_responses.render_obsidian_help(),
            )

        # --- Phase 6: pending pipeline artifacts (read-only) ---
        if sub == "obsidian.pending_artifacts":
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub,
                text=self._obsidian_pending_artifacts(operator_id=operator_id),
            )

        # --- Phase 6: what blocks a note ---
        if sub == "obsidian.what_blocks":
            resolved_ref = self._resolve_note_alias(
                note_ref=intent["params"]["note_ref"], chat_id=chat_id, user_id=user_id
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub,
                text=self._obsidian_what_blocks(
                    operator_id=operator_id,
                    note_ref=resolved_ref,
                    chat_id=chat_id,
                    user_id=user_id,
                ),
            )

        if sub == "obsidian.list_pending":
            text = self._obsidian_list_notes(
                operator_id=operator_id,
                list_fn=list_promotable_notes,
                caption="pendientes (pending_triage)",
                permission="operator.read",
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub, text=text,
            )

        if sub == "obsidian.list_report_ready":
            text = self._obsidian_list_notes(
                operator_id=operator_id,
                list_fn=list_reportable_notes,
                caption="listas para report (promoted_to_draft)",
                permission="operator.read",
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub, text=text,
            )

        if sub == "obsidian.show_note_status":
            resolved_ref = self._resolve_note_alias(
                note_ref=intent["params"]["note_ref"], chat_id=chat_id, user_id=user_id
            )
            text = self._obsidian_show_status(
                note_ref=resolved_ref,
                operator_id=operator_id,
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub, text=text,
            )

        if sub == "obsidian.capture_clarify":
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode,
                intent=sub, text=assistant_responses.render_obsidian_capture_clarify(),
            )

        if sub == "obsidian.capture":
            return self._obsidian_capture(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                title=intent["params"]["title"],
                body=intent["params"]["body"],
                mode=mode,
            )

        if sub == "obsidian.promote_to_draft":
            resolved_ref = self._resolve_note_alias(
                note_ref=intent["params"]["note_ref"], chat_id=chat_id, user_id=user_id
            )
            return self._obsidian_promote(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                note_ref=resolved_ref,
                target="draft",
                mode=mode,
            )

        if sub == "obsidian.promote_to_report":
            resolved_ref = self._resolve_note_alias(
                note_ref=intent["params"]["note_ref"], chat_id=chat_id, user_id=user_id
            )
            return self._obsidian_promote(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                note_ref=resolved_ref,
                target="report",
                mode=mode,
            )

        # --- Phase 5: last N notes ---
        if sub == "obsidian.list_last_n":
            text = self._vault_list_last_n(
                operator_id=operator_id,
                n=intent["params"].get("n", 5),
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode, intent=sub, text=text,
            )

        # --- Phase 5: text search ---
        if sub == "obsidian.search_text":
            text = self._vault_search_text(
                operator_id=operator_id,
                query=intent["params"].get("query", ""),
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode, intent=sub, text=text,
            )

        # --- Phase 5: summary today ---
        if sub == "obsidian.summary_today":
            text = self._vault_summary_today(
                operator_id=operator_id,
                chat_id=chat_id,
                user_id=user_id,
            )
            return self._response(
                chat_id=chat_id, user_id=user_id, operator_id=operator_id,
                action_id="telegram.command", mode=mode, intent=sub, text=text,
            )

        # Unknown obsidian sub-intent — fall back to help
        return self._response(
            chat_id=chat_id, user_id=user_id, operator_id=operator_id,
            action_id="telegram.command", mode=mode,
            intent=sub, text=assistant_responses.render_obsidian_conversation_help(),
        )

    def _obsidian_list_notes(
        self,
        *,
        operator_id: str,
        list_fn: Any,
        caption: str,
        permission: str,
        chat_id: str,
        user_id: str,
    ) -> str:
        if not self._can_operator(operator_id, permission):
            return f"Operador no autorizado para listar notas ({permission})."
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()
        try:
            notes = list_fn(vault_root=vault_root, max_results=10)
        except Exception as exc:
            return f"Error listando notas: {exc}"
        return assistant_responses.render_obsidian_list(notes, caption)

    def _obsidian_show_status(
        self,
        *,
        note_ref: str,
        operator_id: str,
        chat_id: str,
        user_id: str,
    ) -> str:
        if not self._can_operator(operator_id, "operator.read"):
            return "Operador no autorizado para consultar estado de notas."
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()
        try:
            resolved = resolve_note(vault_root, note_ref)
        except Exception as exc:
            return f"Error resolviendo referencia: {exc}"
        if resolved is None:
            return "No hay notas en inbox o vault no accesible."
        if resolved.ambiguous:
            return assistant_responses.render_obsidian_ambiguous(
                resolved.candidates, action="consultar estado"
            )
        if resolved.capture_status == "not_found":
            return assistant_responses.render_error_note_not_found(resolved.note_name)
        # C — save last resolved note in session
        self._save_session_note(chat_id=chat_id, user_id=user_id, note_name=resolved.note_name)
        # Phase 6: enrich with created_at_utc from get_note_status
        full_status = get_note_status(vault_root, resolved.note_name) or {}
        return assistant_responses.render_obsidian_note_status_v2({
            "note_name": resolved.note_name,
            "run_id": resolved.run_id,
            "capture_status": resolved.capture_status,
            "created_at_utc": full_status.get("created_at_utc", "?"),
            "source_dir": "Agent/Inbox_Agent",
        })

    def _obsidian_capture(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        title: str,
        body: str,
        mode: str,
    ) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.write",
            command="obsidian.capture",
            chat_id=chat_id,
            user_id=user_id,
            action_id="action.inbox.write.v1",
        )
        if operator is None:
            return "Operador no autorizado para action.inbox.write.v1."
        effective = self.policy.get_effective_action_state("action.inbox.write.v1")
        if effective is None or not effective.effective_allowed:
            status = effective.status if effective is not None else "unknown"
            return f"La acción inbox.write no está habilitada (status={status})."
        run_id = datetime.now(timezone.utc).strftime("tg-%Y%m%dT%H%M%S")
        body_bytes = len(body.encode("utf-8"))
        summary = f"inbox.write | run_id={run_id} | title={title} | body={body_bytes} B"
        params = {
            "run_id": run_id,
            "capture_title": title,
            "capture_body": body,
            "source_refs": None,
        }
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        self.pending_confirmations[pending_key] = PendingConfirmation(
            intent="inbox_write",
            operator_id=operator_id,
            summary=summary,
            mutation="inbox_write",
            action_id="action.inbox.write.v1",
            params=params,
            reason="telegram_obsidian_capture",
        )
        self._audit_channel_event(
            event="confirmation_requested",
            command="obsidian.capture",
            chat_id=chat_id, user_id=user_id, operator_id=operator_id,
            ok=True,
            action_id="action.inbox.write.v1",
            params={"intent": "inbox_write", "summary": summary},
        )
        return self._response(
            chat_id=chat_id, user_id=user_id, operator_id=operator_id,
            action_id="action.inbox.write.v1",
            mode=mode, intent="inbox_write",
            text=f"Acción interpretada:\n{summary}\nResponde 'si' para ejecutar o 'no' para cancelar.",
        )

    def _obsidian_promote(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        note_ref: str,
        target: str,  # "draft" or "report"
        mode: str,
    ) -> str:
        action_id = "action.draft.promote.v1" if target == "draft" else "action.report.promote.v1"
        mutation = "draft_promote" if target == "draft" else "report_promote"
        command_name = f"obsidian.promote_{target}"

        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="operator.write",
            command=command_name,
            chat_id=chat_id,
            user_id=user_id,
            action_id=action_id,
        )
        if operator is None:
            return f"Operador no autorizado para {action_id}."

        effective = self.policy.get_effective_action_state(action_id)
        if effective is None or not effective.effective_allowed:
            status = effective.status if effective is not None else "unknown"
            return f"La acción {action_id} no está habilitada (status={status})."

        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()

        try:
            resolved = resolve_note(vault_root, note_ref)
        except Exception as exc:
            return f"Error resolviendo referencia: {exc}"

        if resolved is None:
            return "No hay notas en inbox o vault no accesible."
        if resolved.ambiguous:
            return assistant_responses.render_obsidian_ambiguous(
                resolved.candidates, action=f"promover a {target}"
            )
        if resolved.capture_status == "not_found":
            return f"Nota no encontrada: {note_ref}"

        note_name = resolved.note_name
        # C — save last resolved note in session
        self._save_session_note(chat_id=chat_id, user_id=user_id, note_name=note_name)
        summary = f"{target}.promote | note={note_name} (estado: {resolved.capture_status})"
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        self.pending_confirmations[pending_key] = PendingConfirmation(
            intent=mutation,
            operator_id=operator_id,
            summary=summary,
            mutation=mutation,
            action_id=action_id,
            params={"note_name": note_name},
            reason=f"telegram_obsidian_{target}_promote",
        )
        self._audit_channel_event(
            event="confirmation_requested",
            command=command_name,
            chat_id=chat_id, user_id=user_id, operator_id=operator_id,
            ok=True,
            action_id=action_id,
            params={"intent": mutation, "summary": summary},
        )
        return self._response(
            chat_id=chat_id, user_id=user_id, operator_id=operator_id,
            action_id=action_id,
            mode=mode, intent=mutation,
            text=f"Acción interpretada:\n{summary}\nResponde 'si' para ejecutar o 'no' para cancelar.",
        )

    # -----------------------------------------------------------------------
    # Phase 5 — Vault Read Chat handlers (read-only, no mutations)
    # -----------------------------------------------------------------------

    def _vault_read_check(self, operator_id: str) -> str | None:
        """Return error string if operator lacks read permission or vault not set."""
        if not self._can_operator(operator_id, "operator.read"):
            return "Operador no autorizado para leer el vault."
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()
        return None

    def _vault_list_last_n(
        self, *, operator_id: str, n: int, chat_id: str, user_id: str
    ) -> str:
        err = self._vault_read_check(operator_id)
        if err:
            return err
        vault_root = self.policy.vault_inbox.vault_root
        try:
            notes = vault_list_last_n(vault_root, n)
        except Exception as exc:
            return f"Error leyendo vault: {exc}"
        return assistant_responses.render_vault_last_n(notes, n)

    def _vault_search_text(
        self, *, operator_id: str, query: str, chat_id: str, user_id: str
    ) -> str:
        err = self._vault_read_check(operator_id)
        if err:
            return err
        if not query or len(query) < 2:
            return "Búsqueda demasiado corta. Usa al menos 2 caracteres."
        vault_root = self.policy.vault_inbox.vault_root
        try:
            notes = vault_search_notes(vault_root, query)
        except Exception as exc:
            return f"Error buscando en vault: {exc}"
        return assistant_responses.render_vault_search(notes, query)

    def _vault_summary_today(
        self, *, operator_id: str, chat_id: str, user_id: str
    ) -> str:
        err = self._vault_read_check(operator_id)
        if err:
            return err
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        vault_root = self.policy.vault_inbox.vault_root
        try:
            notes = vault_summarize_today(vault_root)
        except Exception as exc:
            return f"Error leyendo vault: {exc}"
        return assistant_responses.render_vault_summary_today(notes, today)

    # -----------------------------------------------------------------------
    # Phase 6 — Operational Hygiene helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _render_promote_error(*, note_name: str, code: str, target: str) -> str:
        """Return a conversational error message for a promotion failure."""
        if code == "staging_conflict":
            return assistant_responses.render_error_staging_conflict(note_name)
        if code == "report_conflict":
            return assistant_responses.render_error_report_conflict(note_name)
        if code == "not_promotable":
            return assistant_responses.render_error_not_promotable(note_name)
        if code == "not_reportable":
            return assistant_responses.render_error_not_reportable(note_name)
        if code == "not_found":
            return assistant_responses.render_error_note_not_found(note_name)
        return f"Error promoviendo a {target}.\ncode={code}\nnota={note_name}"

    def _obsidian_pending_artifacts(self, *, operator_id: str) -> str:
        """Read-only: show presence of STAGED_INPUT.md and REPORT_INPUT.md."""
        if not self._can_operator(operator_id, "operator.read"):
            return "Operador no autorizado para leer el vault."
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()
        try:
            status = read_pending_artifacts(vault_root)
        except Exception as exc:
            return f"Error inspeccionando artefactos: {exc}"
        return assistant_responses.render_pending_artifacts(
            staged_exists=status.staged_exists,
            report_exists=status.report_exists,
            staged_note_name=status.staged_note_name,
            report_note_name=status.report_note_name,
        )

    def _obsidian_what_blocks(
        self, *, operator_id: str, note_ref: str, chat_id: str = "", user_id: str = ""
    ) -> str:
        """Read-only: explain what blocks a note from promotion."""
        if not self._can_operator(operator_id, "operator.read"):
            return "Operador no autorizado para leer el vault."
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return assistant_responses.render_obsidian_vault_not_configured()
        try:
            resolved = resolve_note(vault_root, note_ref)
        except Exception as exc:
            return f"Error resolviendo referencia: {exc}"
        if resolved is None:
            return "No hay notas en inbox o vault no accesible."
        if resolved.ambiguous:
            return assistant_responses.render_obsidian_ambiguous(
                resolved.candidates, action="consultar bloqueo"
            )
        if resolved.capture_status == "not_found":
            return assistant_responses.render_error_note_not_found(note_ref)
        # C — save last resolved note in session
        if chat_id and user_id:
            self._save_session_note(chat_id=chat_id, user_id=user_id, note_name=resolved.note_name)
        return assistant_responses.render_what_blocks(
            note_name=resolved.note_name,
            capture_status=resolved.capture_status,
        )

    @staticmethod
    def _split_command(text: str) -> tuple[str, str]:
        command, _, remainder = text.strip().partition(" ")
        return command, remainder.strip()

    def _parse_execute_arguments(self, argument_text: str) -> tuple[str, dict[str, Any]]:
        if not argument_text:
            raise PolicyError("uso: /execute <action_id> [k=v ...]")
        parts = argument_text.split()
        if len(parts) > 8:
            raise PolicyError("demasiados parámetros")
        action_id = parts[0].strip()
        raw_params = self._parse_key_value_tokens(parts[1:])
        if action_id == "action.health.general.v1":
            if raw_params:
                raise PolicyError("health no acepta parámetros")
            return action_id, {}
        if action_id == "action.logs.read.v1":
            stream_id = raw_params.get("stream_id")
            if not isinstance(stream_id, str) or not stream_id:
                raise PolicyError("stream_id requerido")
            params = {"stream_id": stream_id}
            if "tail_lines" in raw_params:
                try:
                    params["tail_lines"] = int(raw_params["tail_lines"])
                except ValueError as exc:
                    raise PolicyError("tail_lines debe ser entero") from exc
            return action_id, params
        if action_id == "action.webhook.trigger.v1":
            for key in ("target_id", "event_type", "note"):
                if key not in raw_params or not raw_params[key]:
                    raise PolicyError(f"{key} requerido")
            return action_id, {
                "target_id": raw_params["target_id"],
                "event_type": raw_params["event_type"],
                "note": raw_params["note"],
            }
        if action_id == "action.openclaw.restart.v1":
            if raw_params:
                raise PolicyError("restart no acepta parámetros")
            return action_id, {}
        if action_id == "action.dropzone.write.v1":
            for key in ("filename", "content"):
                if key not in raw_params or not raw_params[key]:
                    raise PolicyError(f"{key} requerido")
            return action_id, {
                "filename": raw_params["filename"],
                "content": raw_params["content"],
            }
        raise PolicyError("action_id no soportado por el adaptador Telegram")

    @staticmethod
    def _parse_key_value_tokens(tokens: list[str]) -> dict[str, str]:
        params: dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise PolicyError("parámetros deben ser k=v")
            key, value = token.split("=", 1)
            key = key.strip()
            value = urllib.parse.unquote_plus(value.strip())
            if not key:
                raise PolicyError("clave vacía en parámetros")
            if len(key) > 64:
                raise PolicyError("clave de parámetro demasiado larga")
            if len(value) > 512:
                raise PolicyError("valor de parámetro demasiado largo")
            params[key] = value
        return params

    @staticmethod
    def _safe_params_for_audit(params: dict[str, Any]) -> dict[str, Any]:
        safe = dict(params)
        if "content" in safe and isinstance(safe["content"], str):
            safe["content_bytes"] = len(safe["content"].encode("utf-8"))
            del safe["content"]
        return safe

    def _audit_channel_event(
        self,
        *,
        event: str,
        command: str,
        chat_id: str,
        user_id: str,
        operator_id: str | None,
        ok: bool,
        operator_role: str | None = None,
        action_id: str = "telegram.command",
        params: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        code: str | None = None,
    ) -> None:
        payload = {
            "command": command,
            "telegram_chat_id": chat_id,
            "telegram_user_id": user_id,
        }
        if params:
            payload.update(params)
        self.audit.write(
            event=event,
            action_id=action_id,
            actor=operator_id or "telegram",
            operator_id=operator_id,
            operator_role=operator_role,
            authorized=ok if event == "telegram_command_executed" else None,
            params=payload,
            ok=ok,
            result=result,
            error=error,
            code=code,
        )

    @staticmethod
    def _limit_message(text: str, maximum: int = 3000) -> str:
        if len(text) <= maximum:
            return text
        return text[: maximum - 20] + "\n...[truncated]..."

    def _render_execution_result(self, result: BrokerResult) -> str:
        if result.ok:
            return self._limit_message(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return self._limit_message(
            f"execute failed\naction_id={result.action_id}\ncode={result.code}\nerror={result.error}"
        )

    @staticmethod
    def _render_mutation_result(*, ok: bool, summary: str, action_id: str) -> str:
        if ok:
            return f"Acción aplicada.\n{summary}\naction_id={action_id}"
        return f"No se pudo aplicar la acción.\n{summary}\naction_id={action_id}"

    def _wake_assistant(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        self.session_store.wake(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        self._audit_channel_event(
            event="assistant_wake",
            command="/wake",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            params={"timeout_seconds": self.assistant_idle_timeout_seconds},
        )
        # A — vault context on wake
        vault_ctx = self._build_wake_vault_context(operator_id=operator_id)
        wake_text = (
            "Asistente despierto.\n"
            f"Timeout por inactividad: {self.assistant_idle_timeout_seconds}s.\n"
            "Puedes pedirme estado general, capacidades activas, auditoría reciente, logs permitidos,\n"
            "explicación del estado o propuestas de acción. Para salir: /sleep."
            + vault_ctx
        )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id="telegram.command",
            mode="assistant",
            intent="assistant_wake",
            text=wake_text,
        )

    def _build_wake_vault_context(self, *, operator_id: str) -> str:
        """A — Collect vault summary for the /wake message. Soft failures silently omit fields."""
        if not self._can_operator(operator_id, "operator.read"):
            return ""
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return ""
        pending_count: int | None = None
        staged_exists: bool | None = None
        report_exists: bool | None = None
        last_event: str | None = None
        try:
            notes = list_promotable_notes(vault_root=vault_root, max_results=50)
            pending_count = len(notes)
        except Exception:
            pass
        try:
            arts = read_pending_artifacts(vault_root)
            staged_exists = arts.staged_exists
            report_exists = arts.report_exists
        except Exception:
            pass
        try:
            audit_path = Path(self.policy.broker.audit_log_path)
            if audit_path.exists():
                raw_lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for raw in reversed(raw_lines):
                    if raw.strip():
                        try:
                            p = json.loads(raw)
                            ts = p.get("ts", "")[:19]
                            ev = p.get("event", "?")
                            aid = p.get("action_id", "-")
                            last_event = f"{ev} | {aid} | {ts}"
                        except Exception:
                            pass
                        break
        except Exception:
            pass
        return assistant_responses.render_wake_vault_context(
            pending_count=pending_count,
            staged_exists=staged_exists,
            report_exists=report_exists,
            last_event=last_event,
        )

    def _sleep_assistant(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        reason: str,
    ) -> str:
        existed = self.session_store.sleep(chat_id=chat_id, user_id=user_id)
        key = self._pending_key(chat_id=chat_id, user_id=user_id)
        self.pending_confirmations.pop(key, None)
        # C — clear session note memory on sleep
        self._session_last_note.pop(key, None)
        if existed is not None:
            self._audit_channel_event(
                event="assistant_sleep",
                command="/sleep",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=True,
                params={"reason": reason},
            )
        return self._response(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            action_id="telegram.command",
            mode="assistant",
            intent="assistant_sleep",
            text=(
                "Asistente dormido. Mantengo disponibles los slash commands habituales."
                if existed is not None
                else "El asistente ya estaba dormido. Los slash commands siguen disponibles."
            ),
        )

    def _get_active_session(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
    ) -> AssistantSession | None:
        def on_invalidated(reason: str) -> None:
            self.pending_confirmations.pop(self._pending_key(chat_id=chat_id, user_id=user_id), None)
            if reason == "timeout":
                self._audit_channel_event(
                    event="assistant_sleep",
                    command="assistant",
                    chat_id=chat_id,
                    user_id=user_id,
                    operator_id=operator_id,
                    ok=True,
                    params={"reason": "timeout", "timeout_seconds": self.assistant_idle_timeout_seconds},
                )

        return self.session_store.get_active(
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            idle_timeout_seconds=self.assistant_idle_timeout_seconds,
            on_invalidated=on_invalidated,
        )

    def _has_active_session(self, *, chat_id: str, user_id: str, operator_id: str) -> bool:
        return self.session_store.has_active(chat_id=chat_id, user_id=user_id, operator_id=operator_id)

    def _check_mutation_permission(self, *, operator_id: str, action_id: str) -> str | None:
        try:
            self.policy.authorize_operator_for_action_mutation(operator_id, action_id)
            return None
        except PolicyError as exc:
            return str(exc)

    def _response(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        action_id: str,
        text: str,
        mode: str,
        intent: str,
    ) -> str:
        self._audit_channel_event(
            event="response_generated",
            command=mode,
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id=action_id,
            params={"mode": mode, "intent": intent},
            result={"text_preview": text[:200]},
        )
        return text

    def _render_assistant_status(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="policy.read",
            command="assistant",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "No puedo resumir el estado porque este operador no tiene permiso de lectura."
        states = self.policy.list_effective_action_states()
        summary = {"enabled": 0, "disabled": 0, "expired": 0, "consumed": 0}
        for state in states:
            summary[state.status] = summary.get(state.status, 0) + 1
        return assistant_responses.render_assistant_status(
            operator_id=operator.operator_id,
            total_actions=len(states),
            summary=summary,
        )

    def _render_assistant_capabilities(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="policy.read",
            command="assistant",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "No puedo listar capacidades porque este operador no tiene permiso de lectura."
        rows = []
        for state in self.policy.list_effective_action_states():
            can_execute = self._can_operator(operator_id, state.permission)
            rows.append(
                f"- {state.action_id}: status={state.status}, mode={state.mode}, exec={'yes' if can_execute else 'no'}"
            )
        return self._limit_message(assistant_responses.render_assistant_capabilities(rows=rows))

    def _render_assistant_audit_tail(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        body = self._handle_audit_tail(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if body == "Operador no autorizado para consultar auditoría.":
            return body
        return assistant_responses.render_assistant_audit_tail(body)

    def _render_assistant_explanation(self, *, chat_id: str, user_id: str, operator_id: str) -> str:
        operator = self._authorize_operator(
            operator_id=operator_id,
            permission="policy.read",
            command="assistant",
            chat_id=chat_id,
            user_id=user_id,
        )
        if operator is None:
            return "No puedo explicar el estado porque este operador no tiene permiso de lectura."
        states = self.policy.list_effective_action_states()
        disabled = [state.action_id for state in states if state.status == "disabled"]
        consumed = [state.action_id for state in states if state.status == "consumed"]
        expired = [state.action_id for state in states if state.status == "expired"]
        return self._limit_message(
            assistant_responses.render_assistant_explanation(
                operator_id=operator.operator_id,
                disabled=disabled,
                expired=expired,
                consumed=consumed,
            )
        )

    def _render_assistant_suggestion(self, *, operator_id: str) -> str:
        states = self.policy.list_effective_action_states()
        base = assistant_responses.render_assistant_suggestion(operator_id=operator_id, states=states)
        # D — append vault context when available
        vault_addendum = self._build_suggest_vault_context(operator_id=operator_id)
        if vault_addendum:
            return base + vault_addendum
        return base

    def _build_suggest_vault_context(self, *, operator_id: str) -> str:
        """D — Vault-aware context for 'qué propones'."""
        if not self._can_operator(operator_id, "operator.read"):
            return ""
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            return ""
        lines = []
        try:
            pending = list_promotable_notes(vault_root=vault_root, max_results=50)
            if pending:
                lines.append(f"- Hay {len(pending)} nota(s) en pending_triage esperando draft_promote.")
        except Exception:
            pass
        try:
            reportable = list_reportable_notes(vault_root=vault_root, max_results=50)
            if reportable:
                lines.append(f"- Hay {len(reportable)} nota(s) en promoted_to_draft esperando report_promote.")
        except Exception:
            pass
        try:
            arts = read_pending_artifacts(vault_root)
            if arts.staged_exists:
                lines.append("- STAGED_INPUT.md presente: el pipeline de draft aún no ha consumido el artefacto.")
            if arts.report_exists:
                lines.append("- REPORT_INPUT.md presente: el pipeline de report aún no ha consumido el artefacto.")
        except Exception:
            pass
        if not lines:
            return ""
        return "\nVault:\n" + "\n".join(lines)

    @staticmethod
    def _render_assistant_identity(*, operator_id: str) -> str:
        return assistant_responses.render_assistant_identity(operator_id=operator_id)

    @staticmethod
    def _render_assistant_fallback() -> str:
        return assistant_responses.render_assistant_fallback()


def build_logger(log_level: str) -> logging.Logger:
    logger = logging.getLogger("davlos.telegram_bot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def runtime_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_runtime_status(
    *,
    state: str,
    policy_path: str,
    next_offset: int | None,
    last_update_id: int | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ts": runtime_timestamp(),
        "state": state,
        "policy_path": policy_path,
        "next_offset": next_offset,
    }
    if last_update_id is not None:
        payload["last_update_id"] = last_update_id
    if last_error is not None:
        payload["last_error"] = last_error
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DAVLOS OpenClaw Telegram adapter MVP")
    parser.add_argument("--policy", required=True, help="Path to restricted operator policy json")
    parser.add_argument("--once", action="store_true", help="Poll Telegram once and exit")
    parser.add_argument("--log-level", default="INFO", help="Python log level")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = build_logger(args.log_level)
    processor = TelegramCommandProcessor(args.policy)
    if not processor.policy.telegram.enabled:
        raise SystemExit("telegram integration is disabled in policy")
    token = os.environ.get(processor.policy.telegram.bot_token_env, "")
    if not token:
        raise SystemExit(f"missing env var: {processor.policy.telegram.bot_token_env}")

    offset_store = TelegramOffsetStore(processor.policy.telegram.offset_store_path)
    status_store = TelegramRuntimeStatusStore(processor.policy.telegram.runtime_status_path)
    next_offset = offset_store.load()
    backoff_seconds = 1
    status_store.write(
        build_runtime_status(
            state="starting",
            policy_path=args.policy,
            next_offset=next_offset,
        )
    )
    while True:
        try:
            updates = processor.api_client.get_updates(
                offset=next_offset,
                timeout=processor.policy.telegram.poll_timeout_seconds,
            )
            last_update_id: int | None = None
            for update in updates:
                handled_update_id = processor.process_update(update)
                if handled_update_id is not None:
                    last_update_id = handled_update_id
                    next_offset = handled_update_id + 1
                    offset_store.save(next_offset)
            status_store.write(
                build_runtime_status(
                    state="running",
                    policy_path=args.policy,
                    next_offset=next_offset,
                    last_update_id=last_update_id,
                )
            )
            backoff_seconds = 1
            if args.once:
                return 0
            time.sleep(1)
        except (TelegramApiError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            logger.warning("telegram polling failed error=%s backoff_seconds=%s", exc, backoff_seconds)
            status_store.write(
                build_runtime_status(
                    state="degraded",
                    policy_path=args.policy,
                    next_offset=next_offset,
                    last_error=str(exc),
                )
            )
            if args.once:
                return 1
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)


if __name__ == "__main__":
    raise SystemExit(main())
