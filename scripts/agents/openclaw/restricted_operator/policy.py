from __future__ import annotations

import json
from pathlib import Path

from models import (
    ActionPolicy,
    BrokerConfig,
    HealthCheckConfig,
    LogStreamConfig,
    WebhookTargetConfig,
)


class PolicyError(ValueError):
    pass


class PolicyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.raw = self._load_json(self.path)
        self.broker = self._load_broker(self.raw.get("broker", {}))
        self.actions = self._load_actions(self.raw.get("actions", {}))
        self.log_streams = self._load_log_streams(self.raw.get("log_streams", {}))
        self.webhook_targets = self._load_webhook_targets(self.raw.get("webhook_targets", {}))
        self.health_checks = self._load_health_checks(self.raw.get("health_checks", {}))

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
            dropzone_dir=str(payload["dropzone_dir"]),
            max_tail_lines=int(payload["max_tail_lines"]),
            max_write_bytes=int(payload["max_write_bytes"]),
        )

    @staticmethod
    def _load_actions(payload: dict) -> dict[str, ActionPolicy]:
        actions: dict[str, ActionPolicy] = {}
        for action_id, item in payload.items():
            actions[action_id] = ActionPolicy(
                action_id=action_id,
                enabled=bool(item.get("enabled", False)),
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
