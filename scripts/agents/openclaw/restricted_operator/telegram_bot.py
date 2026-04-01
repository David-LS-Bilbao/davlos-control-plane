from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from audit import AuditLogger
from broker import RestrictedOperatorBroker
from models import BrokerRequest, BrokerResult
from policy import PolicyError, PolicyStore


class TelegramApiError(RuntimeError):
    pass


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


class TelegramCommandProcessor:
    def __init__(self, policy_path: str, api_client: TelegramHttpClient | None = None):
        self.policy_path = policy_path
        self.policy = PolicyStore(policy_path)
        self.broker = RestrictedOperatorBroker(policy_path)
        self.audit = AuditLogger(self.policy.broker.audit_log_path)
        token = os.environ.get(self.policy.telegram.bot_token_env, "")
        self.api_client = api_client or TelegramHttpClient(
            api_base_url=self.policy.telegram.api_base_url,
            token=token,
        )

    def process_update(self, update: dict[str, Any]) -> int | None:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        text = message.get("text")
        update_id = update.get("update_id")
        if not isinstance(text, str) or not text.startswith("/"):
            return int(update_id) if isinstance(update_id, int) else None
        chat_id = str(chat.get("id", ""))
        user_id = str(user.get("id", ""))
        reply = self.handle_text(chat_id=chat_id, user_id=user_id, text=text)
        self.api_client.send_message(chat_id=chat_id, text=reply)
        return int(update_id) if isinstance(update_id, int) else None

    def handle_text(self, *, chat_id: str, user_id: str, text: str) -> str:
        command, argument_text = self._split_command(text)
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
            permission="policy.read",
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
    def _split_command(text: str) -> tuple[str, str]:
        command, _, remainder = text.strip().partition(" ")
        return command, remainder.strip()

    def _parse_execute_arguments(self, argument_text: str) -> tuple[str, dict[str, Any]]:
        if not argument_text:
            raise PolicyError("uso: /execute <action_id> [k=v ...]")
        parts = argument_text.split()
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
    def _render_help(operator_id: str) -> str:
        return (
            f"operator={operator_id}\n"
            "/status\n"
            "/capabilities\n"
            "/audit_tail\n"
            "/execute <action_id> [k=v ...]"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DAVLOS OpenClaw Telegram adapter MVP")
    parser.add_argument("--policy", required=True, help="Path to restricted operator policy json")
    parser.add_argument("--once", action="store_true", help="Poll Telegram once and exit")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    processor = TelegramCommandProcessor(args.policy)
    if not processor.policy.telegram.enabled:
        raise SystemExit("telegram integration is disabled in policy")
    token = os.environ.get(processor.policy.telegram.bot_token_env, "")
    if not token:
        raise SystemExit(f"missing env var: {processor.policy.telegram.bot_token_env}")

    offset_store = TelegramOffsetStore(processor.policy.telegram.offset_store_path)
    next_offset = offset_store.load()
    while True:
        updates = processor.api_client.get_updates(
            offset=next_offset,
            timeout=processor.policy.telegram.poll_timeout_seconds,
        )
        for update in updates:
            handled_update_id = processor.process_update(update)
            if handled_update_id is not None:
                next_offset = handled_update_id + 1
                offset_store.save(next_offset)
        if args.once:
            return 0
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
