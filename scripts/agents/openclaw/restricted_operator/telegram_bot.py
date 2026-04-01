from __future__ import annotations

import argparse
import json
import logging
import os
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

from audit import AuditLogger
from broker import RestrictedOperatorBroker
import cli as broker_cli
from models import BrokerRequest, BrokerResult
from policy import PolicyError, PolicyStore


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
    def __init__(self, policy_path: str, api_client: TelegramHttpClient | None = None):
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
            return self._render_help(operator_id)

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
        pending_key = self._pending_key(chat_id=chat_id, user_id=user_id)
        pending = self.pending_confirmations.get(pending_key)
        normalized = self._normalize_text(text)
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
            return self._execute_pending_confirmation(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                pending=pending,
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
            return "Acción cancelada. No se aplicó ningún cambio."
        if pending is not None:
            return (
                "Hay una acción pendiente de confirmación.\n"
                f"{pending.summary}\n"
                "Responde 'si' para ejecutar o 'no' para cancelar."
            )

        intent = self._detect_conversational_intent(text)
        if intent is None:
            self._audit_channel_event(
                event="intent_rejected_unsupported",
                command="conversation",
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                ok=False,
                error="unsupported or ambiguous conversational intent",
                params={"text_preview": text[:120]},
            )
            return self._render_conversation_help()

        self._audit_channel_event(
            event="intent_detected",
            command="conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id=intent["action_id"],
            params={"intent": intent["intent"], "text_preview": text[:120]},
        )
        if intent["intent"] == "status":
            return self._handle_status(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "capabilities":
            return self._handle_capabilities(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "audit_tail":
            return self._handle_audit_tail(chat_id=chat_id, user_id=user_id, operator_id=operator_id)
        if intent["intent"] == "logs_read":
            return self._execute_conversation_broker_action(
                chat_id=chat_id,
                user_id=user_id,
                operator_id=operator_id,
                action_id="action.logs.read.v1",
                params=intent["params"],
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
            command="conversation",
            chat_id=chat_id,
            user_id=user_id,
            operator_id=operator_id,
            ok=True,
            action_id=pending.action_id,
            params={"intent": pending.intent, "summary": pending.summary},
        )
        return (
            "Acción interpretada:\n"
            f"{pending.summary}\n"
            "Responde 'si' para ejecutar o 'no' para cancelar."
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
        return self._render_execution_result(result)

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
        return self._render_mutation_result(
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
    def _pending_key(*, chat_id: str, user_id: str) -> str:
        return f"{chat_id}:{user_id}"

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return " ".join(normalized.lower().strip().split())

    @staticmethod
    def _is_confirmation_accept(normalized: str) -> bool:
        return normalized in {"si", "sí", "confirmar", "confirmo", "ok", "dale"}

    @staticmethod
    def _is_confirmation_reject(normalized: str) -> bool:
        return normalized in {"no", "cancelar", "cancela", "rechazar"}

    def _detect_conversational_intent(self, text: str) -> dict[str, Any] | None:
        normalized = self._normalize_text(text)
        if normalized in {"estado", "estado general", "como va", "como va openclaw", "salud general"}:
            return {"intent": "status", "action_id": "telegram.command", "params": {}}
        if normalized in {
            "capacidades",
            "capacidades activas",
            "que capacidades hay",
            "que capacidades estan activas",
            "capabilities",
        }:
            return {"intent": "capabilities", "action_id": "telegram.command", "params": {}}
        if normalized in {"auditoria", "auditoria reciente", "audit", "audit tail", "ultimos eventos"}:
            return {"intent": "audit_tail", "action_id": "telegram.command", "params": {}}

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

        return None

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
            "webhook": "action.webhook.trigger.v1",
            "restart": "action.openclaw.restart.v1",
        }
        for token in normalized.replace(",", " ").split():
            if token.startswith("action.") and token.endswith(".v1"):
                return token
            if token in aliases:
                return aliases[token]
        return None

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

    @staticmethod
    def _render_conversation_help() -> str:
        return (
            "No entendí la intención o no está soportada.\n"
            "Prueba una de estas frases:\n"
            "- estado general\n"
            "- capacidades activas\n"
            "- auditoría reciente\n"
            "- logs openclaw 20\n"
            "- habilita action.dropzone.write.v1\n"
            "- deshabilita action.dropzone.write.v1\n"
            "- habilita action.dropzone.write.v1 por 15 minutos\n"
            "- resetea one-shot action.webhook.trigger.v1"
        )

    @staticmethod
    def _render_help(operator_id: str) -> str:
        return (
            f"operator={operator_id}\n"
            "/status\n"
            "/capabilities\n"
            "/audit_tail\n"
            "/execute <action_id> [k=v ...]\n"
            "Conversacional: estado general | capacidades activas | auditoría reciente | logs openclaw 20"
        )


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
