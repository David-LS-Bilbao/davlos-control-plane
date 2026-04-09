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
    OperatorAuthConfig,
    OperatorRecord,
    TelegramConfig,
    TelegramPrincipalRecord,
    WebhookTargetConfig,
)
from state_store import LockedJsonStateStore, StateStoreError


class PolicyError(ValueError):
    pass


DEFAULT_ROLE_PERMISSIONS = {
    "viewer": ["policy.read", "operator.read"],
    "operator": ["policy.read", "policy.mutate", "operator.read", "operator.trigger", "operator.write"],
    "admin": [
        "policy.read",
        "policy.mutate",
        "operator.audit",
        "operator.read",
        "operator.trigger",
        "operator.write",
        "operator.control",
    ],
}


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
        self.operator_auth = self._load_operator_auth(self.raw.get("operator_auth", {}))
        self.telegram = self._load_telegram(self.raw.get("telegram", {}))
        self.state_store_path = Path(self.broker.state_store_path)
        self.runtime_store = LockedJsonStateStore(self.state_store_path)
        self.runtime_state = self._load_runtime_state()

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
    def _load_operator_auth(payload: dict) -> OperatorAuthConfig:
        roles_payload = payload.get("roles", DEFAULT_ROLE_PERMISSIONS)
        if not isinstance(roles_payload, dict):
            raise PolicyError("operator_auth.roles must be an object")
        roles: dict[str, list[str]] = {}
        for role_name, permissions in roles_payload.items():
            if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
                raise PolicyError(f"invalid permissions for role: {role_name}")
            roles[str(role_name)] = [str(item) for item in permissions]

        operators_payload = payload.get("operators", {})
        if not isinstance(operators_payload, dict):
            raise PolicyError("operator_auth.operators must be an object")
        operators: dict[str, OperatorRecord] = {}
        for operator_id, item in operators_payload.items():
            if not isinstance(item, dict):
                raise PolicyError(f"invalid operator record: {operator_id}")
            role = str(item.get("role", "viewer"))
            if role not in roles:
                raise PolicyError(f"unknown operator role for {operator_id}: {role}")
            operators[str(operator_id)] = OperatorRecord(
                operator_id=str(operator_id),
                role=role,
                enabled=bool(item.get("enabled", True)),
                display_name=str(item["display_name"]) if item.get("display_name") is not None else None,
                reason=str(item["reason"]) if item.get("reason") is not None else None,
            )
        return OperatorAuthConfig(roles=roles, operators=operators)

    @staticmethod
    def _load_telegram_principals(payload: dict, field_name: str) -> dict[str, TelegramPrincipalRecord]:
        if not isinstance(payload, dict):
            raise PolicyError(f"{field_name} must be an object")
        principals: dict[str, TelegramPrincipalRecord] = {}
        for principal_id, item in payload.items():
            if not isinstance(item, dict):
                raise PolicyError(f"invalid telegram principal record: {field_name}.{principal_id}")
            operator_id = item.get("operator_id")
            if not isinstance(operator_id, str) or not operator_id:
                raise PolicyError(f"missing operator_id for {field_name}.{principal_id}")
            principals[str(principal_id)] = TelegramPrincipalRecord(
                principal_id=str(principal_id),
                operator_id=operator_id,
                enabled=bool(item.get("enabled", True)),
                display_name=str(item["display_name"]) if item.get("display_name") is not None else None,
                reason=str(item["reason"]) if item.get("reason") is not None else None,
            )
        return principals

    @staticmethod
    def _load_telegram(payload: dict) -> TelegramConfig:
        if not payload:
            return TelegramConfig(
                enabled=False,
                bot_token_env="OPENCLAW_TELEGRAM_BOT_TOKEN",
                api_base_url="https://api.telegram.org",
                poll_timeout_seconds=20,
                audit_tail_lines=10,
                offset_store_path="/opt/automation/agents/openclaw/broker/state/telegram_offset.json",
                runtime_status_path="/opt/automation/agents/openclaw/broker/state/telegram_runtime_status.json",
                rate_limit_window_seconds=30,
                rate_limit_max_requests=6,
                max_command_length=512,
                allowed_chats={},
                allowed_users={},
            )
        if not isinstance(payload, dict):
            raise PolicyError("telegram must be an object")
        return TelegramConfig(
            enabled=bool(payload.get("enabled", False)),
            bot_token_env=str(payload.get("bot_token_env", "OPENCLAW_TELEGRAM_BOT_TOKEN")),
            api_base_url=str(payload.get("api_base_url", "https://api.telegram.org")),
            poll_timeout_seconds=int(payload.get("poll_timeout_seconds", 20)),
            audit_tail_lines=int(payload.get("audit_tail_lines", 10)),
            offset_store_path=str(
                payload.get(
                    "offset_store_path",
                    "/opt/automation/agents/openclaw/broker/state/telegram_offset.json",
                )
            ),
            runtime_status_path=str(
                payload.get(
                    "runtime_status_path",
                    "/opt/automation/agents/openclaw/broker/state/telegram_runtime_status.json",
                )
            ),
            rate_limit_window_seconds=int(payload.get("rate_limit_window_seconds", 30)),
            rate_limit_max_requests=int(payload.get("rate_limit_max_requests", 6)),
            max_command_length=int(payload.get("max_command_length", 512)),
            allowed_chats=PolicyStore._load_telegram_principals(
                payload.get("allowed_chats", {}),
                "telegram.allowed_chats",
            ),
            allowed_users=PolicyStore._load_telegram_principals(
                payload.get("allowed_users", {}),
                "telegram.allowed_users",
            ),
        )

    def _load_runtime_state(self) -> dict[str, dict]:
        try:
            return self.runtime_store.load_actions()
        except StateStoreError as exc:
            raise PolicyError(str(exc)) from exc

    def refresh_runtime_state(self) -> dict[str, dict]:
        self.runtime_state = self._load_runtime_state()
        return self.runtime_state

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
        runtime_state = self.refresh_runtime_state()
        return self._get_effective_action_state_from_runtime(action_id, runtime_state=runtime_state, now=now)

    def _get_effective_action_state_from_runtime(
        self,
        action_id: str,
        *,
        runtime_state: dict[str, dict],
        now: datetime | None = None,
    ) -> EffectiveActionState | None:
        declared = self.actions.get(action_id)
        if declared is None:
            return None
        now = now or datetime.now(timezone.utc)
        override = runtime_state.get(action_id, {})
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
        runtime_state = self.refresh_runtime_state()
        states: list[EffectiveActionState] = []
        for action_id in sorted(self.actions):
            state = self._get_effective_action_state_from_runtime(action_id, runtime_state=runtime_state, now=now)
            if state is not None:
                states.append(state)
        return states

    def authorize_operator(self, operator_id: str | None, permission: str) -> OperatorRecord:
        if not operator_id:
            raise PolicyError("operator_id is required")
        operator = self.operator_auth.operators.get(operator_id)
        if operator is None or not operator.enabled:
            raise PolicyError(f"operator is not authorized: {operator_id}")
        granted_permissions = set(self.operator_auth.roles.get(operator.role, []))
        if permission not in granted_permissions:
            raise PolicyError(f"operator lacks permission {permission}: {operator_id}")
        return operator

    def authorize_operator_for_action_mutation(
        self,
        operator_id: str | None,
        action_id: str,
    ) -> OperatorRecord:
        declared = self.actions.get(action_id)
        if declared is None:
            raise PolicyError(f"unknown action_id: {action_id}")
        operator = self.authorize_operator(operator_id, "policy.mutate")
        self.authorize_operator(operator_id, declared.permission)
        return operator

    def resolve_telegram_operator(
        self,
        *,
        chat_id: str | None,
        user_id: str | None,
    ) -> tuple[TelegramPrincipalRecord | None, str | None]:
        if chat_id:
            chat_record = self.telegram.allowed_chats.get(chat_id)
            if chat_record is not None and chat_record.enabled:
                return chat_record, chat_record.operator_id
        if user_id:
            user_record = self.telegram.allowed_users.get(user_id)
            if user_record is not None and user_record.enabled:
                return user_record, user_record.operator_id
        return None, None

    def consume_one_shot(
        self,
        action_id: str,
        *,
        used_at: datetime | None = None,
        updated_by: str = "broker",
        reason: str = "consumed_after_valid_execution",
    ) -> None:
        used_at = used_at or datetime.now(timezone.utc)
        self._mutate_runtime_state(
            action_id,
            lambda action_state: self._apply_one_shot_consumed(
                action_state,
                used_at=used_at,
                updated_by=updated_by,
                reason=reason,
            ),
        )

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
        self._mutate_runtime_state(
            action_id,
            lambda action_state: self._apply_one_shot_reset(
                action_state,
                updated_by=updated_by,
                reason=reason,
            ),
        )

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
        self._mutate_runtime_state(
            action_id,
            lambda action_state: self._apply_enabled(
                action_state,
                enabled=enabled,
                updated_by=updated_by,
                reason=reason or ("enabled_via_cli" if enabled else "disabled_via_cli"),
            ),
        )

    def set_action_enabled_with_expiration(
        self,
        action_id: str,
        *,
        enabled: bool,
        expires_at: datetime | None,
        updated_by: str = "cli",
        reason: str | None = None,
    ) -> None:
        declared = self.actions.get(action_id)
        if declared is None:
            raise PolicyError(f"unknown action_id: {action_id}")
        self._mutate_runtime_state(
            action_id,
            lambda action_state: self._apply_enabled_with_expiration(
                action_state,
                enabled=enabled,
                expires_at=expires_at,
                updated_by=updated_by,
                reason=reason or ("enabled_with_expiration_via_cli" if enabled else "disabled_via_cli"),
            ),
        )

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
        self._mutate_runtime_state(
            action_id,
            lambda action_state: self._apply_expiration(
                action_state,
                expires_at=expires_at,
                updated_by=updated_by,
                reason=reason or "updated_expiration_via_cli",
            ),
        )

    def _mutate_runtime_state(self, action_id: str, mutator) -> None:
        try:
            self.runtime_state = self.runtime_store.update_actions(
                lambda actions: mutator(actions.setdefault(action_id, {}))
            )
        except StateStoreError as exc:
            raise PolicyError(str(exc)) from exc

    @staticmethod
    def _apply_one_shot_consumed(
        action_state: dict[str, object],
        *,
        used_at: datetime,
        updated_by: str,
        reason: str,
    ) -> None:
        action_state["one_shot_consumed"] = True
        action_state["consumed_at"] = used_at.isoformat().replace("+00:00", "Z")
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason

    @staticmethod
    def _apply_one_shot_reset(
        action_state: dict[str, object],
        *,
        updated_by: str,
        reason: str,
    ) -> None:
        action_state["one_shot_consumed"] = False
        action_state.pop("consumed_at", None)
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason

    @staticmethod
    def _apply_enabled(
        action_state: dict[str, object],
        *,
        enabled: bool,
        updated_by: str,
        reason: str,
    ) -> None:
        action_state["enabled"] = enabled
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason

    @staticmethod
    def _apply_enabled_with_expiration(
        action_state: dict[str, object],
        *,
        enabled: bool,
        expires_at: datetime | None,
        updated_by: str,
        reason: str,
    ) -> None:
        action_state["enabled"] = enabled
        action_state["expires_at"] = (
            expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if expires_at is not None
            else None
        )
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason

    @staticmethod
    def _apply_expiration(
        action_state: dict[str, object],
        *,
        expires_at: datetime | None,
        updated_by: str,
        reason: str,
    ) -> None:
        action_state["expires_at"] = (
            expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if expires_at is not None
            else None
        )
        action_state["updated_by"] = updated_by
        action_state["reason"] = reason
