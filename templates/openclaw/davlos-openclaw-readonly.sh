#!/usr/bin/env bash
set -euo pipefail

readonly DATE_BIN="/usr/bin/date"
readonly JOURNALCTL_BIN="/usr/bin/journalctl"
readonly PYTHON_BIN="/usr/bin/python3"

readonly RUNTIME_POLICY_PATH="/opt/automation/agents/openclaw/broker/restricted_operator_policy.json"
readonly FALLBACK_POLICY_PATH="/opt/control-plane/templates/openclaw/restricted_operator_policy.json"
readonly DEFAULT_AUDIT_LINES="20"
readonly DEFAULT_UNIT_LOG_LINES="6"

usage() {
  echo "Usage: $0 {runtime_summary|broker_state_console|broker_audit_recent|telegram_runtime_status|operational_logs_recent}" >&2
  exit 64
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: this helper must run as root" >&2
    exit 1
  fi
}

require_deps() {
  for bin in "${DATE_BIN}" "${JOURNALCTL_BIN}" "${PYTHON_BIN}"; do
    if [[ ! -x "${bin}" ]]; then
      echo "ERROR: missing required binary: ${bin}" >&2
      exit 1
    fi
  done
}

print_header() {
  local mode="$1"
  echo "== davlos openclaw readonly =="
  echo "mode=${mode}"
  echo "timestamp=$("${DATE_BIN}" -u +%FT%TZ)"
}

run_python_helper() {
  local mode="$1"
  "${PYTHON_BIN}" - "${mode}" "${RUNTIME_POLICY_PATH}" "${FALLBACK_POLICY_PATH}" "${DEFAULT_AUDIT_LINES}" <<'PY'
from __future__ import annotations

import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except PermissionError:
        return False


def parse_optional_datetime(value):
    if value in (None, ""):
        return None
    normalized = value[:-1] + "+00:00" if isinstance(value, str) and value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def choose_policy(runtime_policy: Path, fallback_policy: Path):
    if safe_exists(runtime_policy):
        return runtime_policy, "runtime"
    if safe_exists(fallback_policy):
        return fallback_policy, "repo_fallback"
    raise SystemExit("ERROR: no policy file available")


def load_policy(runtime_policy: Path, fallback_policy: Path):
    policy_path, policy_source = choose_policy(runtime_policy, fallback_policy)
    raw = load_json(policy_path)
    broker = raw.get("broker", {})
    actions = raw.get("actions", {})
    telegram = raw.get("telegram", {})
    runtime_state_path = Path(str(broker.get("state_store_path", "")))
    audit_log_path = Path(str(broker.get("audit_log_path", "")))
    telegram_runtime_path = Path(str(telegram.get("runtime_status_path", "")))
    runtime_actions = {}
    if safe_exists(runtime_state_path):
        try:
            payload = load_json(runtime_state_path)
            runtime_actions = payload.get("actions", {})
            if not isinstance(runtime_actions, dict):
                raise SystemExit("ERROR: runtime state actions must be an object")
        except PermissionError:
            runtime_actions = {}
    return {
        "policy_path": str(policy_path),
        "policy_source": policy_source,
        "actions": actions,
        "runtime_actions": runtime_actions,
        "runtime_state_path": runtime_state_path,
        "audit_log_path": audit_log_path,
        "telegram_runtime_path": telegram_runtime_path,
    }


def summarize_states(config):
    now = datetime.now(timezone.utc)
    rows = []
    summary = {"enabled": 0, "disabled": 0, "expired": 0, "consumed": 0}
    for action_id in sorted(config["actions"]):
        declared = config["actions"][action_id]
        override = config["runtime_actions"].get(action_id, {})
        enabled = bool(override.get("enabled", declared.get("enabled", False)))
        mode = str(override.get("mode", declared.get("mode", "restricted")))
        expires_dt = parse_optional_datetime(override.get("expires_at")) if "expires_at" in override else parse_optional_datetime(declared.get("expires_at"))
        one_shot = bool(override.get("one_shot", declared.get("one_shot", False)))
        one_shot_consumed = bool(override.get("one_shot_consumed", False))
        reason = override.get("reason") if override.get("reason") is not None else declared.get("reason")
        permission = str(declared.get("permission", "unset"))
        expires_at = expires_dt.isoformat().replace("+00:00", "Z") if expires_dt else None
        status = "enabled"
        allowed = True
        if not enabled:
            status = "disabled"
            allowed = False
        elif expires_dt is not None and expires_dt <= now:
            status = "expired"
            allowed = False
        elif one_shot and one_shot_consumed:
            status = "consumed"
            allowed = False
        summary[status] = summary.get(status, 0) + 1
        suffix = []
        if one_shot:
            suffix.append(f"one_shot={'yes' if one_shot else 'no'}")
            suffix.append(f"consumed={'yes' if one_shot_consumed else 'no'}")
        if expires_at:
            suffix.append(f"expires_at={expires_at}")
        if reason:
            suffix.append(f"reason={reason}")
        rows.append(
            "{action_id} | status={status} | mode={mode} | allowed={allowed} | permission={permission}{suffix}".format(
                action_id=action_id,
                status=status,
                mode=mode,
                allowed="yes" if allowed else "no",
                permission=permission,
                suffix=f" | {' | '.join(suffix)}" if suffix else "",
            )
        )
    return summary, rows


def runtime_summary(config):
    print(f"policy_source={config['policy_source']}")
    print(f"policy_path={config['policy_path']}")
    print(f"runtime_state_path={config['runtime_state_path']}")
    print(f"runtime_state_exists={'yes' if safe_exists(config['runtime_state_path']) else 'no'}")
    print(f"audit_log_path={config['audit_log_path']}")
    print(f"audit_log_exists={'yes' if safe_exists(config['audit_log_path']) else 'no'}")
    print(f"telegram_runtime_path={config['telegram_runtime_path']}")
    print(f"telegram_runtime_exists={'yes' if safe_exists(config['telegram_runtime_path']) else 'no'}")


def broker_state_console(config):
    summary, rows = summarize_states(config)
    print(f"policy_source={config['policy_source']}")
    print(f"policy_path={config['policy_path']}")
    print("scope=restricted_operator_capabilities")
    print(
        "summary total={total} enabled={enabled} disabled={disabled} expired={expired} consumed={consumed}".format(
            total=len(rows),
            enabled=summary.get("enabled", 0),
            disabled=summary.get("disabled", 0),
            expired=summary.get("expired", 0),
            consumed=summary.get("consumed", 0),
        )
    )
    print("legend readonly=view restricted=mutate allowed=can_execute now")
    for row in rows:
        print(row)


def broker_audit_recent(config, lines: int):
    path = config["audit_log_path"]
    if not safe_exists(path):
        print("policy_source={}".format(config["policy_source"]))
        print("scope=restricted_operator_audit lines=0")
        print("no_events=yes")
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        raw_lines = [line.rstrip("\n") for line in deque(handle, maxlen=lines)]
    print(f"policy_source={config['policy_source']}")
    print(f"scope=restricted_operator_audit lines={len(raw_lines)}")
    for line in raw_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print("raw_event parse_error=yes")
            continue
        parts = [
            f"ts={event.get('ts', '?')}",
            f"event={event.get('event', '?')}",
            f"action_id={event.get('action_id', '-')}",
            f"ok={event.get('ok')}",
        ]
        if event.get("operator_id"):
            parts.append(f"operator_id={event.get('operator_id')}")
        if event.get("operator_role"):
            parts.append(f"operator_role={event.get('operator_role')}")
        if event.get("code"):
            parts.append(f"code={event.get('code')}")
        if event.get("error"):
            parts.append(f"error={event.get('error')}")
        print(" | ".join(parts))


def redact_payload(payload):
    if isinstance(payload, dict):
        redacted = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if any(token in key_lower for token in ("token", "apikey", "api_key", "authorization", "secret")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload


def telegram_runtime_status(config):
    path = config["telegram_runtime_path"]
    if not safe_exists(path):
        raise SystemExit(f"ERROR: telegram runtime status not found: {path}")
    payload = load_json(path)
    print(json.dumps(redact_payload(payload), indent=2, sort_keys=True))


def main():
    mode = sys.argv[1]
    runtime_policy = Path(sys.argv[2])
    fallback_policy = Path(sys.argv[3])
    default_audit_lines = int(sys.argv[4])
    config = load_policy(runtime_policy, fallback_policy)
    if mode == "runtime_summary":
        runtime_summary(config)
        return
    if mode == "broker_state_console":
        broker_state_console(config)
        return
    if mode == "broker_audit_recent":
        broker_audit_recent(config, default_audit_lines)
        return
    if mode == "telegram_runtime_status":
        telegram_runtime_status(config)
        return
    raise SystemExit(f"ERROR: unsupported mode {mode}")


main()
PY
}

runtime_summary() {
  print_header "runtime_summary"
  run_python_helper "runtime_summary"
}

broker_state_console() {
  print_header "broker_state_console"
  run_python_helper "broker_state_console"
}

broker_audit_recent() {
  print_header "broker_audit_recent"
  run_python_helper "broker_audit_recent"
}

telegram_runtime_status() {
  print_header "telegram_runtime_status"
  run_python_helper "telegram_runtime_status"
}

operational_logs_recent() {
  local unit output
  # Fixed allowlist by design: recent operational context without granting
  # arbitrary journald access through sudo.
  local allowed_units=(
    "openclaw-telegram-bot.service"
    "inference-gateway.service"
    "obsidian-vault-backup.service"
    "obsidian-vault-restore-check.service"
    "openclaw-boundary-backup.service"
  )
  print_header "operational_logs_recent"
  echo "lines_per_unit=${DEFAULT_UNIT_LOG_LINES}"
  for unit in "${allowed_units[@]}"; do
    echo "-- unit=${unit} --"
    output="$("${JOURNALCTL_BIN}" -u "${unit}" -n "${DEFAULT_UNIT_LOG_LINES}" --no-pager --output=short-iso --quiet 2>/dev/null || true)"
    if [[ -z "${output}" || "${output}" == "-- No entries --" ]]; then
      echo "no_entries=yes"
    else
      printf '%s\n' "${output}"
    fi
  done
}

main() {
  require_root
  require_deps
  if [[ $# -ne 1 ]]; then
    usage
  fi
  case "$1" in
    runtime_summary) runtime_summary ;;
    broker_state_console) broker_state_console ;;
    broker_audit_recent) broker_audit_recent ;;
    telegram_runtime_status) telegram_runtime_status ;;
    operational_logs_recent) operational_logs_recent ;;
    *) usage ;;
  esac
}

main "$@"
