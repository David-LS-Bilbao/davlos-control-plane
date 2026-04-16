"""Sandbox LLM agent — conversational interface backed by the local Ollama inference gateway.

Used exclusively in sandbox mode (Phase 9). All mutations still go through the broker.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import deque
from typing import Any

_ACTION_RE = re.compile(r"<action>(.*?)</action>", re.DOTALL)

_DEFAULT_SYSTEM_PROMPT = (
    "Eres OpenClaw, asistente de gestión de conocimiento integrado con un vault Obsidian.\n"
    "Responde siempre en español de forma natural y concisa.\n"
    "\n"
    "Acciones disponibles (úsalas solo si el usuario lo pide explícitamente):\n"
    "- action.inbox.write.v1: Captura idea al inbox. Params: title (str), body (str)\n"
    "- action.draft.promote.v1: Promueve nota a draft. Params: note_name (str)\n"
    "- action.report.promote.v1: Promueve nota a report. Params: note_name (str)\n"
    "- action.note.create.v1: Crea nota en carpeta. Params: folder (str), title (str), body (str)\n"
    "- action.note.archive.v1: Archiva una nota. Params: note_path (str)\n"
    "- action.note.edit.v1: Edita nota existente. Params: note_path (str), mode ('append'|'replace'), content (str)\n"
    "- action.note.move.v1: Mueve nota a otra carpeta. Params: note_path (str), dest_folder (str)\n"
    "\n"
    "Para ejecutar una acción incluye al FINAL de tu respuesta EXACTAMENTE esto:\n"
    '<action>{"action_id": "...", "params": {...}}</action>\n'
    "\n"
    "Incluye <action> SOLO si el usuario te pide explícitamente realizar algo.\n"
    "No incluyas <action> al responder preguntas o dar información.\n"
)


class SandboxLLMAgentError(RuntimeError):
    pass


class SandboxLLMAgent:
    """Conversational LLM agent backed by a local OpenAI-compatible inference server."""

    def __init__(
        self,
        *,
        inference_url: str = "http://127.0.0.1:11440/v1/chat/completions",
        model: str = "qwen2.5:3b",
        max_history_turns: int = 6,
        timeout_seconds: int = 30,
        system_prompt_template: str = _DEFAULT_SYSTEM_PROMPT,
    ):
        self.inference_url = inference_url
        self.model = model
        self.max_history_turns = max_history_turns
        self.timeout_seconds = timeout_seconds
        self.system_prompt_template = system_prompt_template
        # Per-session conversation history. Key: "chat_id:user_id"
        self._history: dict[str, deque[dict[str, str]]] = {}

    def chat(
        self, *, key: str, message: str, vault_summary: str = ""
    ) -> tuple[str, dict[str, Any] | None]:
        """Send a message and return (clean_text, action_dict | None).

        action_dict is parsed from an <action>{...}</action> tag if present.
        The tag is stripped from the returned text.
        """
        history = self._history.setdefault(key, deque())
        history.append({"role": "user", "content": message})
        max_messages = self.max_history_turns * 2

        system = self.system_prompt_template
        if vault_summary:
            system += f"\nEstado actual del vault:\n{vault_summary}"

        messages = [{"role": "system", "content": system}] + list(history)
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 512,
        }).encode("utf-8")
        req = urllib.request.Request(self.inference_url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            history.pop()  # roll back user message on failure
            raise SandboxLLMAgentError(f"inference request failed: {exc}") from exc

        raw_text = self._extract_text(payload)
        action = self._parse_action(raw_text)
        clean = _ACTION_RE.sub("", raw_text).strip()
        history.append({"role": "assistant", "content": clean})
        # Trim after both messages are appended: keep at most max_history_turns full turns
        while len(history) > max_messages:
            history.popleft()
        return clean, action

    def clear_history(self, key: str) -> None:
        self._history.pop(key, None)

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise SandboxLLMAgentError("inference response has no choices")
        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise SandboxLLMAgentError("inference response content is empty")
        return content.strip()

    @staticmethod
    def _parse_action(text: str) -> dict[str, Any] | None:
        """Extract and parse the first <action>{...}</action> tag, if any."""
        match = _ACTION_RE.search(text)
        if not match:
            return None
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or "action_id" not in data:
            return None
        if not isinstance(data.get("params"), dict):
            data["params"] = {}
        return data
