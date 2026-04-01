from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionPolicy:
    action_id: str
    enabled: bool
    permission: str
    description: str


@dataclass(frozen=True)
class BrokerConfig:
    bind_host: str
    bind_port: int
    audit_log_path: str
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
        return payload
