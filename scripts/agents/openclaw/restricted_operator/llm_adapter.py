from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    provider: str
    model: str
    api_key: str
    timeout_seconds: int


class LLMAdapter:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or self.from_env()

    @staticmethod
    def from_env() -> LLMSettings:
        enabled = os.environ.get("OPENCLAW_LLM_ENABLED", "false").strip().lower() == "true"
        timeout_seconds = 8
        if enabled:
            timeout_raw = os.environ.get("OPENCLAW_LLM_TIMEOUT_SECONDS", "8").strip() or "8"
            try:
                timeout_seconds = max(1, int(timeout_raw))
            except ValueError as exc:
                raise LLMAdapterError("OPENCLAW_LLM_TIMEOUT_SECONDS must be an integer") from exc
        return LLMSettings(
            enabled=enabled,
            provider=os.environ.get("OPENCLAW_LLM_PROVIDER", "gemini").strip().lower() or "gemini",
            model=os.environ.get("OPENCLAW_LLM_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
            api_key=os.environ.get("OPENCLAW_LLM_API_KEY", "").strip(),
            timeout_seconds=timeout_seconds,
        )

    def is_enabled(self) -> bool:
        return self.settings.enabled

    def interpret(self, *, text: str) -> dict[str, Any]:
        if not self.settings.enabled:
            raise LLMAdapterError("llm adapter is disabled")
        if self.settings.provider != "gemini":
            raise LLMAdapterError(f"unsupported llm provider: {self.settings.provider}")
        if not self.settings.api_key:
            raise LLMAdapterError("OPENCLAW_LLM_API_KEY is required when OPENCLAW_LLM_ENABLED=true")
        return self._call_gemini(text=text)

    def _call_gemini(self, *, text: str) -> dict[str, Any]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(self.settings.model, safe='')}:generateContent"
            f"?key={urllib.parse.quote(self.settings.api_key, safe='')}"
        )
        prompt = (
            "Eres un clasificador cerrado para DAVLOS OpenClaw Telegram. "
            "Devuelve solo JSON válido sin markdown ni texto adicional. "
            "Claves exactas: intent, action_id, params, needs_confirmation, reply_style. "
            "No inventes claves extra. "
            "Intents permitidos: "
            "status, capabilities, audit_tail, logs_read, explain_status, suggest_action, "
            "enable_capability, disable_capability, enable_capability_with_ttl, reset_one_shot, unsupported. "
            "Para status/capabilities/audit_tail/explain_status/suggest_action/unsupported usa action_id=telegram.command y params={}. "
            "Para logs_read usa action_id=action.logs.read.v1 y params con stream_id y opcionalmente tail_lines. "
            "Para mutaciones usa el action_id concreto y params vacíos salvo enable_capability_with_ttl, que requiere ttl_minutes entero. "
            "reply_style debe ser brief. "
            "needs_confirmation=true para mutaciones; false para lectura. "
            f"Mensaje del operador: {text}"
        )
        body = {
            "system_instruction": {
                "parts": [{"text": "Clasifica intención en JSON estricto para un asistente seguro de Telegram."}]
            },
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        raw = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=raw, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", "replace") or "{}")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LLMAdapterError(f"llm request failed: {exc}") from exc
        text_output = self._extract_text(payload)
        try:
            return json.loads(text_output)
        except json.JSONDecodeError as exc:
            raise LLMAdapterError("llm returned invalid json") from exc

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMAdapterError("llm response has no candidates")
        content = candidates[0].get("content", {})
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise LLMAdapterError("llm response has no parts")
        fragments: list[str] = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                fragments.append(part["text"])
        text = "".join(fragments).strip()
        if not text:
            raise LLMAdapterError("llm response text is empty")
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        return text
