from __future__ import annotations

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
        action_policy = self.policy.actions.get(request.action_id)
        if action_policy is None:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id is unknown",
                code="unknown_action",
            )
            self._audit(request, result, {})
            return result
        if not action_policy.enabled:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="action_id is disabled by policy",
                code="forbidden",
            )
            self._audit(request, result, {})
            return result
        action = self.registry.get(request.action_id)
        if action is None:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error="handler is not implemented",
                code="not_implemented",
            )
            self._audit(request, result, {})
            return result
        audit_params = {}
        try:
            if not isinstance(request.params, dict):
                raise ActionError("invalid_params", "params must be an object")
            audit_params = action.audit_params(request.params)
            result = action.execute(request.params)
            if not result.audit_params:
                result.audit_params = audit_params
            self._audit(request, result, result.audit_params)
            return result
        except ActionError as exc:
            result = BrokerResult(
                ok=False,
                action_id=request.action_id,
                error=exc.message,
                code=exc.code,
                audit_params=audit_params,
            )
            self._audit(request, result, audit_params)
            return result

    def _audit(self, request: BrokerRequest, result: BrokerResult, audit_params: dict[str, Any]) -> None:
        self.audit.write(
            action_id=request.action_id,
            actor=request.actor,
            params=audit_params,
            ok=result.ok,
            result=result.result or None,
            error=result.error,
            code=result.code,
        )
