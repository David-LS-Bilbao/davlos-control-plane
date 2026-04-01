from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:
    def __init__(self, path: str):
        self.path = Path(path)

    def write(
        self,
        *,
        event: str,
        action_id: str,
        actor: str,
        params: dict,
        ok: bool,
        operator_id: str | None = None,
        operator_role: str | None = None,
        authorized: bool | None = None,
        result: dict | None = None,
        error: str | None = None,
        code: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "action_id": action_id,
            "actor": actor,
            "params": params,
            "ok": ok,
        }
        if operator_id is not None:
            record["operator_id"] = operator_id
        if operator_role is not None:
            record["operator_role"] = operator_role
        if authorized is not None:
            record["authorized"] = authorized
        if result:
            record["result"] = result
        if error:
            record["error"] = error
        if code:
            record["code"] = code
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
