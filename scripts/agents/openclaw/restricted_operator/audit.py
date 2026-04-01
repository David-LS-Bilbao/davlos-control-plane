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
        action_id: str,
        actor: str,
        params: dict,
        ok: bool,
        result: dict | None = None,
        error: str | None = None,
        code: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action_id": action_id,
            "actor": actor,
            "params": params,
            "ok": ok,
        }
        if result:
            record["result"] = result
        if error:
            record["error"] = error
        if code:
            record["code"] = code
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
