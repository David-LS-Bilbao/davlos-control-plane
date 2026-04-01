from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit import AuditLogger
from policy import PolicyError, PolicyStore, parse_optional_datetime


def resolve_operator_id(operator_id: str | None, updated_by: str | None) -> str | None:
    if operator_id:
        return operator_id
    if updated_by and updated_by != "cli":
        return updated_by
    return updated_by


def require_operator_permission(
    store: PolicyStore,
    *,
    action_id: str,
    operator_id: str | None,
    reason: str,
    mutation: str,
) -> tuple[bool, str | None]:
    try:
        operator = store.authorize_operator(operator_id, "policy.mutate")
        return True, operator.role
    except PolicyError as exc:
        AuditLogger(store.broker.audit_log_path).write(
            event="operator_authorization_rejected",
            action_id=action_id,
            actor=operator_id or "unknown",
            operator_id=operator_id,
            params={"mutation": mutation, "reason": reason},
            ok=False,
            authorized=False,
            error=str(exc),
            code="operator_not_authorized",
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "operator_not_authorized",
                    "detail": str(exc),
                    "operator_id": operator_id,
                },
                indent=2,
            )
        )
        return False, None


def parse_cli_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return parse_optional_datetime(value, "cli.datetime")


def dump_states(store: PolicyStore, at: datetime | None) -> int:
    rows = []
    for state in store.list_effective_action_states(now=at):
        rows.append(
            {
                "action_id": state.action_id,
                "enabled": state.enabled,
                "mode": state.mode,
                "expires_at": state.expires_at,
                "one_shot": state.one_shot,
                "one_shot_consumed": state.one_shot_consumed,
                "effective_allowed": state.effective_allowed,
                "status": state.status,
                "reason": state.reason,
                "updated_by": state.updated_by,
                "permission": state.permission,
            }
        )
    print(json.dumps({"actions": rows}, indent=2, sort_keys=True))
    return 0


def validate_policy(policy_path: str) -> int:
    ok, errors = PolicyStore.validate_policy(policy_path)
    if ok:
        print(json.dumps({"ok": True, "errors": []}, indent=2))
        return 0
    audit_path = ""
    try:
        store = PolicyStore(policy_path)
        audit_path = store.broker.audit_log_path
    except Exception:
        try:
            raw = json.loads(open(policy_path, "r", encoding="utf-8").read())
            audit_path = str(raw.get("broker", {}).get("audit_log_path", ""))
        except Exception:
            audit_path = ""
    if audit_path:
        AuditLogger(audit_path).write(
            event="policy_validation_error",
            action_id="policy.validate",
            actor="cli",
            params={"policy_path": policy_path},
            ok=False,
            error="; ".join(errors),
            code="policy_validation_error",
        )
    print(json.dumps({"ok": False, "errors": errors}, indent=2))
    return 1


def consume_one_shot(
    policy_path: str,
    action_id: str,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    store = PolicyStore(policy_path)
    resolved_operator_id = resolve_operator_id(operator_id, updated_by)
    authorized, operator_role = require_operator_permission(
        store,
        action_id=action_id,
        operator_id=resolved_operator_id,
        reason=reason,
        mutation="consume_one_shot",
    )
    if not authorized:
        return 1
    state = store.get_effective_action_state(action_id)
    if state is None:
        print(json.dumps({"ok": False, "error": "unknown_action"}, indent=2))
        return 1
    if not state.one_shot:
        print(json.dumps({"ok": False, "error": "action_is_not_one_shot"}, indent=2))
        return 1
    store.mark_one_shot_used(action_id, updated_by=resolved_operator_id or updated_by, reason=reason)
    AuditLogger(store.broker.audit_log_path).write(
        event="action_consumed_one_shot",
        action_id=action_id,
        actor=resolved_operator_id or updated_by,
        operator_id=resolved_operator_id,
        operator_role=operator_role,
        authorized=True,
        params={"reason": reason, "source": "cli"},
        ok=True,
        result={"effective_status": "consumed"},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "status": "consumed"}, indent=2))
    return 0


def reset_one_shot(
    policy_path: str,
    action_id: str,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    try:
        store = PolicyStore(policy_path)
        resolved_operator_id = resolve_operator_id(operator_id, updated_by)
        authorized, operator_role = require_operator_permission(
            store,
            action_id=action_id,
            operator_id=resolved_operator_id,
            reason=reason,
            mutation="reset_one_shot",
        )
        if not authorized:
            return 1
        store.reset_one_shot(action_id, updated_by=resolved_operator_id or updated_by, reason=reason)
    except PolicyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    AuditLogger(store.broker.audit_log_path).write(
        event="policy_state_changed",
        action_id=action_id,
        actor=resolved_operator_id or updated_by,
        operator_id=resolved_operator_id,
        operator_role=operator_role,
        authorized=True,
        params={"change": "reset_one_shot", "reason": reason},
        ok=True,
        result={"one_shot_consumed": False},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "one_shot_consumed": False}, indent=2))
    return 0


def set_enabled(
    policy_path: str,
    action_id: str,
    enabled: bool,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    try:
        store = PolicyStore(policy_path)
        resolved_operator_id = resolve_operator_id(operator_id, updated_by)
        authorized, operator_role = require_operator_permission(
            store,
            action_id=action_id,
            operator_id=resolved_operator_id,
            reason=reason,
            mutation="set_enabled",
        )
        if not authorized:
            return 1
        store.set_action_enabled(
            action_id,
            enabled=enabled,
            updated_by=resolved_operator_id or updated_by,
            reason=reason,
        )
    except PolicyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    AuditLogger(store.broker.audit_log_path).write(
        event="policy_state_changed",
        action_id=action_id,
        actor=resolved_operator_id or updated_by,
        operator_id=resolved_operator_id,
        operator_role=operator_role,
        authorized=True,
        params={"change": "enabled", "value": enabled, "reason": reason},
        ok=True,
        result={"enabled": enabled},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "enabled": enabled}, indent=2))
    return 0


def enable_with_optional_ttl(
    policy_path: str,
    action_id: str,
    *,
    ttl_minutes: int | None,
    expires_at: str | None,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    rc = set_enabled(policy_path, action_id, True, operator_id, updated_by, reason)
    if rc != 0:
        return rc
    if ttl_minutes is None and expires_at is None:
        return 0
    return set_ttl(
        policy_path,
        action_id,
        ttl_minutes=ttl_minutes,
        expires_at=expires_at,
        updated_by=updated_by,
        reason=reason,
    )


def set_ttl(
    policy_path: str,
    action_id: str,
    *,
    ttl_minutes: int | None,
    expires_at: str | None,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    if ttl_minutes is None and expires_at is None:
        print(json.dumps({"ok": False, "error": "ttl_minutes_or_expires_at_required"}, indent=2))
        return 1
    try:
        store = PolicyStore(policy_path)
        resolved_operator_id = resolve_operator_id(operator_id, updated_by)
        authorized, operator_role = require_operator_permission(
            store,
            action_id=action_id,
            operator_id=resolved_operator_id,
            reason=reason,
            mutation="set_ttl",
        )
        if not authorized:
            return 1
        if ttl_minutes is not None:
            effective_expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        else:
            effective_expiry = parse_optional_datetime(expires_at, "cli.expires_at")
        store.set_action_expiration(
            action_id,
            expires_at=effective_expiry,
            updated_by=resolved_operator_id or updated_by,
            reason=reason,
        )
    except (PolicyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    expires_at_value = effective_expiry.isoformat().replace("+00:00", "Z") if effective_expiry else None
    AuditLogger(store.broker.audit_log_path).write(
        event="policy_state_changed",
        action_id=action_id,
        actor=resolved_operator_id or updated_by,
        operator_id=resolved_operator_id,
        operator_role=operator_role,
        authorized=True,
        params={"change": "expires_at", "value": expires_at_value, "reason": reason},
        ok=True,
        result={"expires_at": expires_at_value},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "expires_at": expires_at_value}, indent=2))
    return 0


def clear_ttl(
    policy_path: str,
    action_id: str,
    operator_id: str | None,
    updated_by: str,
    reason: str,
) -> int:
    try:
        store = PolicyStore(policy_path)
        resolved_operator_id = resolve_operator_id(operator_id, updated_by)
        authorized, operator_role = require_operator_permission(
            store,
            action_id=action_id,
            operator_id=resolved_operator_id,
            reason=reason,
            mutation="clear_ttl",
        )
        if not authorized:
            return 1
        store.set_action_expiration(
            action_id,
            expires_at=None,
            updated_by=resolved_operator_id or updated_by,
            reason=reason,
        )
    except PolicyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    AuditLogger(store.broker.audit_log_path).write(
        event="policy_state_changed",
        action_id=action_id,
        actor=resolved_operator_id or updated_by,
        operator_id=resolved_operator_id,
        operator_role=operator_role,
        authorized=True,
        params={"change": "expires_at", "value": None, "reason": reason},
        ok=True,
        result={"expires_at": None},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "expires_at": None}, indent=2))
    return 0


def audit_tail(policy_path: str, lines: int) -> int:
    try:
        store = PolicyStore(policy_path)
    except PolicyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    audit_path = Path(store.broker.audit_log_path)
    if not audit_path.exists():
        print(json.dumps({"ok": True, "events": []}, indent=2))
        return 0
    raw_lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events = []
    for line in raw_lines[-lines:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line, "parse_error": True})
    print(json.dumps({"ok": True, "events": events}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DAVLOS restricted operator policy CLI")
    parser.add_argument("--policy", required=True, help="Path to policy json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Show effective action states")
    show_parser.add_argument("--at", help="Optional ISO8601 UTC timestamp to simulate effective state")

    subparsers.add_parser("validate", help="Validate policy json")

    consume_parser = subparsers.add_parser("consume-one-shot", help="Mark a one-shot action as consumed")
    consume_parser.add_argument("--action-id", required=True)
    consume_parser.add_argument("--operator-id")
    consume_parser.add_argument("--updated-by", default="cli")
    consume_parser.add_argument("--reason", default="manually_marked_used")

    reset_parser = subparsers.add_parser("reset-one-shot", help="Reset consumed state for a one-shot action")
    reset_parser.add_argument("--action-id", required=True)
    reset_parser.add_argument("--operator-id")
    reset_parser.add_argument("--updated-by", default="cli")
    reset_parser.add_argument("--reason", default="manually_reset_one_shot")

    enable_parser = subparsers.add_parser("enable", help="Enable an action")
    enable_parser.add_argument("--action-id", required=True)
    enable_parser.add_argument("--ttl-minutes", type=int)
    enable_parser.add_argument("--expires-at")
    enable_parser.add_argument("--operator-id")
    enable_parser.add_argument("--updated-by", default="cli")
    enable_parser.add_argument("--reason", default="enabled_via_cli")

    disable_parser = subparsers.add_parser("disable", help="Disable an action")
    disable_parser.add_argument("--action-id", required=True)
    disable_parser.add_argument("--operator-id")
    disable_parser.add_argument("--updated-by", default="cli")
    disable_parser.add_argument("--reason", default="disabled_via_cli")

    ttl_parser = subparsers.add_parser("set-ttl", help="Set action expiry by ttl minutes or absolute timestamp")
    ttl_parser.add_argument("--action-id", required=True)
    ttl_parser.add_argument("--ttl-minutes", type=int)
    ttl_parser.add_argument("--expires-at")
    ttl_parser.add_argument("--operator-id")
    ttl_parser.add_argument("--updated-by", default="cli")
    ttl_parser.add_argument("--reason", default="ttl_set_via_cli")

    clear_ttl_parser = subparsers.add_parser("clear-ttl", help="Clear action expiry override")
    clear_ttl_parser.add_argument("--action-id", required=True)
    clear_ttl_parser.add_argument("--operator-id")
    clear_ttl_parser.add_argument("--updated-by", default="cli")
    clear_ttl_parser.add_argument("--reason", default="ttl_cleared_via_cli")

    audit_parser = subparsers.add_parser("audit-tail", help="Show recent audit events")
    audit_parser.add_argument("--lines", type=int, default=20)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "validate":
        return validate_policy(args.policy)
    try:
        store = PolicyStore(args.policy)
    except PolicyError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1
    if args.command == "show":
        return dump_states(store, parse_cli_datetime(args.at))
    if args.command == "consume-one-shot":
        return consume_one_shot(args.policy, args.action_id, args.operator_id, args.updated_by, args.reason)
    if args.command == "reset-one-shot":
        return reset_one_shot(args.policy, args.action_id, args.operator_id, args.updated_by, args.reason)
    if args.command == "enable":
        return enable_with_optional_ttl(
            args.policy,
            args.action_id,
            ttl_minutes=args.ttl_minutes,
            expires_at=args.expires_at,
            operator_id=args.operator_id,
            updated_by=args.updated_by,
            reason=args.reason,
        )
    if args.command == "disable":
        return set_enabled(args.policy, args.action_id, False, args.operator_id, args.updated_by, args.reason)
    if args.command == "set-ttl":
        return set_ttl(
            args.policy,
            args.action_id,
            ttl_minutes=args.ttl_minutes,
            expires_at=args.expires_at,
            operator_id=args.operator_id,
            updated_by=args.updated_by,
            reason=args.reason,
        )
    if args.command == "clear-ttl":
        return clear_ttl(args.policy, args.action_id, args.operator_id, args.updated_by, args.reason)
    if args.command == "audit-tail":
        return audit_tail(args.policy, args.lines)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
