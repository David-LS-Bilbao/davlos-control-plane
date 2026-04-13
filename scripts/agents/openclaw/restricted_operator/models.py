from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ActionPolicy:
    action_id: str
    enabled: bool
    mode: str
    expires_at: datetime | None
    one_shot: bool
    reason: str | None
    updated_by: str | None
    permission: str
    description: str


@dataclass(frozen=True)
class BrokerConfig:
    bind_host: str
    bind_port: int
    audit_log_path: str
    state_store_path: str
    dropzone_dir: str
    max_tail_lines: int
    max_write_bytes: int


@dataclass(frozen=True)
class LogStreamConfig:
    stream_id: str
    path: str
    tail_lines_default: int


@dataclass(frozen=True)
class WebhookTargetConfig:
    target_id: str
    url: str
    method: str
    timeout_seconds: int


@dataclass(frozen=True)
class HealthCheckConfig:
    check_id: str
    url: str
    expect_status: int


@dataclass(frozen=True)
class OperatorRecord:
    operator_id: str
    role: str
    enabled: bool
    display_name: str | None
    reason: str | None


@dataclass(frozen=True)
class OperatorAuthConfig:
    roles: dict[str, list[str]]
    operators: dict[str, OperatorRecord]


@dataclass(frozen=True)
class VaultInboxConfig:
    vault_root: str


@dataclass(frozen=True)
class TelegramPrincipalRecord:
    principal_id: str
    operator_id: str
    enabled: bool
    display_name: str | None
    reason: str | None


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    bot_token_env: str
    api_base_url: str
    poll_timeout_seconds: int
    audit_tail_lines: int
    offset_store_path: str
    runtime_status_path: str
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    max_command_length: int
    allowed_chats: dict[str, TelegramPrincipalRecord]
    allowed_users: dict[str, TelegramPrincipalRecord]


@dataclass
class BrokerRequest:
    action_id: str
    params: dict[str, Any] = field(default_factory=dict)
    actor: str = "openclaw"


@dataclass
class BrokerResult:
    ok: bool
    action_id: str
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    code: str | None = None
    event: str | None = None
    audit_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "action_id": self.action_id,
        }
        if self.result:
            payload["result"] = self.result
        if self.error:
            payload["error"] = self.error
        if self.code:
            payload["code"] = self.code
        if self.event:
            payload["event"] = self.event
        return payload


@dataclass(frozen=True)
class EffectiveActionState:
    action_id: str
    enabled: bool
    mode: str
    expires_at: str | None
    one_shot: bool
    one_shot_consumed: bool
    reason: str | None
    updated_by: str | None
    permission: str
    description: str
    effective_allowed: bool
    status: str
