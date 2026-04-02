from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class IntentSchemaError(ValueError):
    pass


ALLOWED_INTENTS = {
    "status",
    "capabilities",
    "audit_tail",
    "logs_read",
    "explain_status",
    "suggest_action",
    "enable_capability",
    "disable_capability",
    "enable_capability_with_ttl",
    "reset_one_shot",
    "unsupported",
}

ALLOWED_REPLY_STYLES = {"brief"}
LLM_OUTPUT_KEYS = {"intent", "action_id", "params", "needs_confirmation", "reply_style"}


@dataclass(frozen=True)
class StructuredIntent:
    intent: str
    action_id: str
    params: dict[str, Any]
    needs_confirmation: bool
    reply_style: str


def _require_keys(payload: dict[str, Any]) -> None:
    payload_keys = set(payload.keys())
    if payload_keys != LLM_OUTPUT_KEYS:
        extras = sorted(payload_keys - LLM_OUTPUT_KEYS)
        missing = sorted(LLM_OUTPUT_KEYS - payload_keys)
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extras:
            details.append(f"extra={','.join(extras)}")
        raise IntentSchemaError("invalid llm output keys" + (f" ({'; '.join(details)})" if details else ""))


def validate_structured_intent(payload: Any) -> StructuredIntent:
    if not isinstance(payload, dict):
        raise IntentSchemaError("llm output must be a JSON object")
    _require_keys(payload)
    intent = payload["intent"]
    action_id = payload["action_id"]
    params = payload["params"]
    needs_confirmation = payload["needs_confirmation"]
    reply_style = payload["reply_style"]

    if not isinstance(intent, str) or intent not in ALLOWED_INTENTS:
        raise IntentSchemaError("intent not allowed")
    if not isinstance(action_id, str) or not action_id:
        raise IntentSchemaError("action_id must be a non-empty string")
    if not isinstance(params, dict):
        raise IntentSchemaError("params must be an object")
    if not isinstance(needs_confirmation, bool):
        raise IntentSchemaError("needs_confirmation must be boolean")
    if not isinstance(reply_style, str) or reply_style not in ALLOWED_REPLY_STYLES:
        raise IntentSchemaError("reply_style not allowed")

    if intent in {"status", "capabilities", "audit_tail", "explain_status", "suggest_action", "unsupported"}:
        if action_id != "telegram.command":
            raise IntentSchemaError("action_id not allowed for read-only assistant intent")
        if params:
            raise IntentSchemaError("params must be empty for read-only assistant intent")
        if needs_confirmation:
            raise IntentSchemaError("read-only assistant intent cannot require confirmation")
    elif intent == "logs_read":
        if action_id != "action.logs.read.v1":
            raise IntentSchemaError("action_id not allowed for logs_read")
        _validate_logs_params(params)
        if needs_confirmation:
            raise IntentSchemaError("logs_read cannot require confirmation")
    elif intent in {"enable_capability", "disable_capability", "reset_one_shot"}:
        if not action_id.startswith("action.") or not action_id.endswith(".v1"):
            raise IntentSchemaError("action_id not allowed for mutation intent")
        if params:
            raise IntentSchemaError("params must be empty for this mutation intent")
        if not needs_confirmation:
            raise IntentSchemaError("mutation intent requires confirmation")
    elif intent == "enable_capability_with_ttl":
        if not action_id.startswith("action.") or not action_id.endswith(".v1"):
            raise IntentSchemaError("action_id not allowed for ttl mutation intent")
        _validate_ttl_params(params)
        if not needs_confirmation:
            raise IntentSchemaError("mutation intent requires confirmation")

    return StructuredIntent(
        intent=intent,
        action_id=action_id,
        params=dict(params),
        needs_confirmation=needs_confirmation,
        reply_style=reply_style,
    )


def _validate_logs_params(params: dict[str, Any]) -> None:
    keys = set(params.keys())
    if keys - {"stream_id", "tail_lines"}:
        raise IntentSchemaError("unexpected logs_read params")
    stream_id = params.get("stream_id")
    if not isinstance(stream_id, str) or not stream_id:
        raise IntentSchemaError("logs_read.stream_id is required")
    if "tail_lines" in params:
        tail_lines = params["tail_lines"]
        if not isinstance(tail_lines, int) or tail_lines <= 0:
            raise IntentSchemaError("logs_read.tail_lines must be a positive integer")


def _validate_ttl_params(params: dict[str, Any]) -> None:
    if set(params.keys()) != {"ttl_minutes"}:
        raise IntentSchemaError("enable_capability_with_ttl requires only ttl_minutes")
    ttl_minutes = params["ttl_minutes"]
    if not isinstance(ttl_minutes, int) or ttl_minutes <= 0:
        raise IntentSchemaError("ttl_minutes must be a positive integer")


def structured_intent_to_internal(intent: StructuredIntent) -> dict[str, Any]:
    if intent.intent == "logs_read":
        return {
            "intent": "logs_read",
            "action_id": "action.logs.read.v1",
            "params": dict(intent.params),
        }
    if intent.intent == "enable_capability":
        return {
            "intent": "enable_capability",
            "action_id": intent.action_id,
            "mutation": "set_enabled",
            "params": {"enabled": True},
            "reason": "telegram_llm_enable",
            "summary": f"Habilitar {intent.action_id}",
        }
    if intent.intent == "disable_capability":
        return {
            "intent": "disable_capability",
            "action_id": intent.action_id,
            "mutation": "set_enabled",
            "params": {"enabled": False},
            "reason": "telegram_llm_disable",
            "summary": f"Deshabilitar {intent.action_id}",
        }
    if intent.intent == "enable_capability_with_ttl":
        ttl_minutes = int(intent.params["ttl_minutes"])
        return {
            "intent": "enable_capability_with_ttl",
            "action_id": intent.action_id,
            "mutation": "enable_with_ttl",
            "params": {"ttl_minutes": ttl_minutes},
            "reason": "telegram_llm_enable_ttl",
            "summary": f"Habilitar {intent.action_id} durante {ttl_minutes} minutos",
        }
    if intent.intent == "reset_one_shot":
        return {
            "intent": "reset_one_shot",
            "action_id": intent.action_id,
            "mutation": "reset_one_shot",
            "params": {},
            "reason": "telegram_llm_reset_one_shot",
            "summary": f"Resetear one-shot de {intent.action_id}",
        }
    return {
        "intent": intent.intent,
        "action_id": intent.action_id,
        "params": {},
    }
