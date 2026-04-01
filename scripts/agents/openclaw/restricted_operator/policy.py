from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models import (
    ActionPolicy,
    BrokerConfig,
    EffectiveActionState,
    HealthCheckConfig,
    LogStreamConfig,
    WebhookTargetConfig,
)


class PolicyError(ValueError):
    pass


def parse_optional_datetime(value: str | None, field_name: str) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise PolicyError(f"{field_name} must be a string or null")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PolicyError(f"invalid datetime for {field_name}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class PolicyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.raw = self._load_json(self.path)
        self.broker = self._load_broker(self.raw.get("broker", {}))
        self.actions = self._load_actions(self.raw.get("actions", {}))
        self.log_streams = self._load_log_streams(self.raw.get("log_streams", {}))
        self.webhook_targets = self._load_webhook_targets(self.raw.get("webhook_targets", {}))
        self.health_checks = self._load_health_checks(self.raw.get("health_checks", {}))
        self.state_store_path = Path(self.broker.state_store_path)
        self.runtime_state = self._load_runtime_state(self.state_store_path)

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise PolicyError(f"policy file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise PolicyError(f"invalid policy json: {path}") from exc

    @staticmethod
    def _load_broker(payload: dict) -> BrokerConfig:
        required = [
            "bind_host",
            "bind_port",
            "audit_log_path",
            "state_store_path",
            "dropzone_dir",
            "max_tail_lines",
            "max_write_bytes",
        ]
        for key in required:
            if key not in payload:
                raise PolicyError(f"missing broker key: {key}")
        return BrokerConfig(
            bind_host=str(payload["bind_host"]),
            bind_port=int(payload["bind_port"]),
            audit_log_path=str(payload["audit_log_path"]),
            state_store_path=str(payload["state_store_path"]),
            dropzone_dir=str(payload["dropzone_dir"]),
            max_tail_lines=int(payload["max_tail_lines"]),
            max_write_bytes=int(payload["max_write_bytes"]),
        )

    @staticmethod
    def _load_actions(payload: dict) -> dict[str, ActionPolicy]:
        actions: dict[str, ActionPolicy] = {}
        for action_id, item in payload.items():
            mode = str(item.get("mode", "restricted"))
            if mode not in {"readonly", "restricted"}:
                raise PolicyError(f"invalid mode for {action_id}")
            actions[action_id] = ActionPolicy(
                action_id=action_id,
                enabled=bool(item.get("enabled", False)),
                mode=mode,
                expires_at=parse_optional_datetime(item.get("expires_at"), f"{action_id}.expires_at"),
                one_shot=bool(item.get("one_shot", False)),
                reason=str(item["reason"]) if item.get("reason") is not None else None,
                updated_by=str(item["updated_by"]) if item.get("updated_by") is not None else None,
                permission=str(item.get("permission", "unset")),
                description=str(item.get("description", "")),
            )
        return actions

    @staticmethod
    def _load_log_streams(payload: dict) -> dict[str, LogStreamConfig]:
        streams: dict[str, LogStreamConfig] = {}
        for stream_id, item in payload.items():
            streams[stream_id] = LogStreamConfig(
                stream_id=stream_id,
                path=str(item["path"]),
                tail_lines_default=int(item.get("tail_lines_default", 50)),
            )
        return streams

    @staticmethod
    def _load_webhook_targets(payload: dict) -> dict[str, WebhookTargetConfig]:
        targets: dict[str, WebhookTargetConfig] = {}
        for target_id, item in payload.items():
            targets[target_id] = WebhookTargetConfig(
                target_id=target_id,
                url=str(item["url"]),
                method=str(item.get("method", "POST")).upper(),
                timeout_seconds=int(item.get("timeout_seconds", 5)),
            )
        return targets

    @staticmethod
    def _load_health_checks(payload: dict) -> dict[str, HealthCheckConfig]:
        checks: dict[str, HealthCheckConfig] = {}
        for check_id, item in payload.items():
            checks[check_id] = HealthCheckConfig(
                check_id=check_id,
                url=str(item["url"]),
                expect_status=int(item.get("expect_status", 200)),
            )
        return checks

    @staticmethod
    def _load_runtime_state(path: Path) -> dict[str, dict]:
        if not path.exists():
            return {}
        payload = PolicyStore._load_json(path)
        actions = payload.get("actions", {})
        if not isinstance(actions, dict):
            raise PolicyError("runtime state actions must be an object")
        return actions

    @staticmethod
    def validate_policy(path: str | Path) -> tuple[bool, list[str]]:
        try:
            PolicyStore(path)
            return True, []
        except PolicyError as exc:
            return False, [str(exc)]

    def get_effective_action_state(
        self,
        action_id: str,
        *,
        now: datetime | None = None,
    ) -> EffectiveActionState | None:
        declared = self.actions.get(action_id)
        if declared is None:
            return None
        now = now or datetime.now(timezone.utc)
        override = self.runtime_state.get(action_id, {})
        enabled = bool(override.get("enabled", declared.enabled))
        mode = str(override.get("mode", declared.mode))
        expires_dt = parse_optional_datetime(
            override.get("expires_at"),
            f"runtime_state.{action_id}.expires_at",
        ) if "expires_at" in override else declared.expires_at
        one_shot = bool(override.get("one_shot", declared.one_shot))
        one_shot_consumed = bool(override.get("one_shot_consumed", False))
        reason = str(override["reason"]) if override.get("reason") is not None else declared.reason
        updated_by = str(override["updated_by"]) if override.get("updated_by") is not None else declared.updated_by
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
        return EffectiveActionState(
            action_id=action_id,
            enabled=enabled,
            mode=mode,
            expires_at=expires_at,
            one_shot=one_shot,
            one_shot_consumed=one_shot_consumed,
            reason=reason,
            updated_by=updated_by,
            permission=declared.permission,
            description=declared.description,
            effective_allowed=allowed,
            status=status,
        )

    def list_effective_action_states(self, *, now: datetime | None = None) -> list[EffectiveActionState]:
        states: list[EffectiveActionState] = []
        for action_id in sorted(self.actions):
            state = self.get_effective_action_state(action_id, now=now)
            if state is not None:
                states.append(state)
        return states

    def consume_one_shot(
        self,
        action_id: str,
        *,
        used_at: datetime | None = None,
        updated_by: str = "broker",
        reason: str = "consumed_after_valid_execution",
    ) -> None:
        used_at = used_at or datetime.now(timezone.utc)
        action_state = self.runtime_state.setdefault(action_id, {})
        action_state["one_shot_consumed"] = True
        action_state["consumed_at"] = used_at.isoformat().replace("+00:00", "Z")
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason
        self._persist_runtime_state()

    def mark_one_shot_used(
        self,
        action_id: str,
        *,
        updated_by: str = "cli",
        reason: str = "manually_marked_used",
    ) -> None:
        self.consume_one_shot(action_id, updated_by=updated_by, reason=reason)

    def reset_one_shot(
        self,
        action_id: str,
        *,
        updated_by: str = "cli",
        reason: str = "manually_reset_one_shot",
    ) -> None:
        declared = self.actions.get(action_id)
        if declared is None:
            raise PolicyError(f"unknown action_id: {action_id}")
        if not declared.one_shot:
            raise PolicyError(f"action is not one_shot: {action_id}")
        action_state = self.runtime_state.setdefault(action_id, {})
        action_state["one_shot_consumed"] = False
        action_state.pop("consumed_at", None)
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason
        self._persist_runtime_state()

    def set_action_enabled(
        self,
        action_id: str,
        *,
        enabled: bool,
        updated_by: str = "cli",
        reason: str | None = None,
    ) -> None:
        declared = self.actions.get(action_id)
        if declared is None:
            raise PolicyError(f"unknown action_id: {action_id}")
        action_state = self.runtime_state.setdefault(action_id, {})
        action_state["enabled"] = enabled
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason or ("enabled_via_cli" if enabled else "disabled_via_cli")
        self._persist_runtime_state()

    def set_action_expiration(
        self,
        action_id: str,
        *,
        expires_at: datetime | None,
        updated_by: str = "cli",
        reason: str | None = None,
    ) -> None:
        declared = self.actions.get(action_id)
        if declared is None:
            raise PolicyError(f"unknown action_id: {action_id}")
        action_state = self.runtime_state.setdefault(action_id, {})
        if expires_at is None:
            action_state["expires_at"] = None
        else:
            action_state["expires_at"] = expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason or "updated_expiration_via_cli"
        self._persist_runtime_state()

    def _persist_runtime_state(self) -> None:
        self.state_store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"actions": self.runtime_state}
        self.state_store_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
