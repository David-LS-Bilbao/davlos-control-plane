from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from intent_schema import IntentSchemaError, structured_intent_to_internal, validate_structured_intent
from llm_adapter import LLMAdapterError


@dataclass(frozen=True)
class RouteDecision:
    intent: dict[str, Any] | None
    source: str
    llm_invoked: bool = False
    llm_validated: bool = False
    llm_rejected_reason: str | None = None


class IntentRouter:
    def __init__(
        self,
        *,
        local_matcher: Callable[[str, bool], dict[str, Any] | None],
        llm_adapter: Any | None = None,
    ):
        self.local_matcher = local_matcher
        self.llm_adapter = llm_adapter

    def route(self, *, text: str, assistant_awake: bool) -> RouteDecision:
        local_intent = self.local_matcher(text, assistant_awake=assistant_awake)
        if local_intent is not None:
            return RouteDecision(intent=local_intent, source="local")
        if not assistant_awake or self.llm_adapter is None or not self.llm_adapter.is_enabled():
            return RouteDecision(intent=None, source="none")
        try:
            raw_output = self.llm_adapter.interpret(text=text)
            structured = validate_structured_intent(raw_output)
            return RouteDecision(
                intent=structured_intent_to_internal(structured),
                source="llm",
                llm_invoked=True,
                llm_validated=True,
            )
        except (IntentSchemaError, LLMAdapterError, ValueError, TypeError) as exc:
            return RouteDecision(
                intent=None,
                source="llm_rejected",
                llm_invoked=True,
                llm_rejected_reason=str(exc),
            )
