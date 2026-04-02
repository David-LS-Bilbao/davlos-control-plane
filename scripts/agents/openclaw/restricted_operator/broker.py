from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from actions import ActionError, build_action_registry
from audit import AuditLogger
from models import BrokerRequest, BrokerResult
from policy import PolicyStore


class RestrictedOperatorBroker:
    def __init__(self, policy_path: str):
        self.policy = PolicyStore(policy_path)
        self.audit = AuditLogger(self.policy.broker.audit_log_path)
        self.registry = build_action_registry(self.policy)

    def execute(self, request: BrokerRequest) -> BrokerResult:
        effective = self.policy.get_effective_action_state(request.action_id)
        if effective is None:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id is unknown",
                code="unknown_action",
                event="action_rejected_unknown",
            )
            self._audit(request, result, {}, event=result.event or "action_rejected_unknown")
            return result
        if effective.status == "disabled":
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id is disabled by policy",
                code="forbidden",
                event="action_rejected_disabled",
                result={"effective_status": effective.status},
            )
            self._audit(request, result, {}, event=result.event or "action_rejected_disabled")
            return result
        if effective.status == "expired":
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id is expired by policy",
                code="forbidden",
                event="action_rejected_expired",
                result={"effective_status": effective.status, "expires_at": effective.expires_at},
            )
            self._audit(request, result, {}, event=result.event or "action_rejected_expired")
            return result
        if effective.status == "consumed":
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id one-shot already consumed",
                code="forbidden",
                event="action_rejected_consumed",
                result={"effective_status": effective.status},
            )
            self._audit(request, result, {}, event=result.event or "action_rejected_consumed")
            return result
        action = self.registry.get(request.action_id)
        if action is None:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="handler is not implemented",
                code="not_implemented",
                event="action_rejected_unimplemented",
            )
            self._audit(request, result, {}, event=result.event or "action_rejected_unimplemented")
            return result
        audit_params = {}
        try:
            if not isinstance(request.params, dict):
                raise ActionError("invalid_params", "params must be an object")
            audit_params = action.audit_params(request.params)
            result = action.execute(request.params)
            if not result.audit_params:
                result.audit_params = audit_params
            result.event = result.event or "action_executed"
            self._audit(request, result, result.audit_params, event=result.event)
            if result.ok and effective.one_shot:
                self.policy.consume_one_shot(
                    request.action_id,
                    used_at=datetime.now(timezone.utc),
                    updated_by=request.actor,
                )
                self.audit.write(
                    event="action_consumed_one_shot",
                    action_id=request.action_id,
                    actor=request.actor,
                    params=result.audit_params,
                    ok=True,
                    result={"effective_status": "consumed"},
                )
            return result
        except ActionError as exc:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error=exc.message,
                code=exc.code,
                event="action_rejected_invalid_params" if exc.code == "invalid_params" else "action_rejected_handler_error",
                audit_params=audit_params,
            )
            self._audit(request, result, audit_params, event=result.event or "action_rejected_handler_error")
            return result

    def _audit(
        self,
        request: BrokerRequest,
        result: BrokerResult,
        audit_params: dict[str, Any],
        *,
        event: str,
    ) -> None:
        self.audit.write(
            event=event,
            action_id=request.action_id,
            actor=request.actor,
            params=audit_params,
            ok=result.ok,
            result=result.result or None,
            error=result.error,
            code=result.code,
        )
