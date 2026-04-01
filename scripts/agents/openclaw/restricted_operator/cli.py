from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from audit import AuditLogger
from policy import PolicyError, PolicyStore, parse_optional_datetime


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


def consume_one_shot(policy_path: str, action_id: str, updated_by: str, reason: str) -> int:
    store = PolicyStore(policy_path)
    state = store.get_effective_action_state(action_id)
    if state is None:
        print(json.dumps({"ok": False, "error": "unknown_action"}, indent=2))
        return 1
    if not state.one_shot:
        print(json.dumps({"ok": False, "error": "action_is_not_one_shot"}, indent=2))
        return 1
    store.mark_one_shot_used(action_id, updated_by=updated_by, reason=reason)
    AuditLogger(store.broker.audit_log_path).write(
        event="action_consumed_one_shot",
        action_id=action_id,
        actor=updated_by,
        params={"reason": reason, "source": "cli"},
        ok=True,
        result={"effective_status": "consumed"},
    )
    print(json.dumps({"ok": True, "action_id": action_id, "status": "consumed"}, indent=2))
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
    consume_parser.add_argument("--updated-by", default="cli")
    consume_parser.add_argument("--reason", default="manually_marked_used")
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
        return consume_one_shot(args.policy, args.action_id, args.updated_by, args.reason)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
