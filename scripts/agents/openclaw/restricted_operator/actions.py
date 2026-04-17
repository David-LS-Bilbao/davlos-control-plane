from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import BrokerResult
from policy import PolicyStore

# vault_inbox_bridge lives one directory up (scripts/agents/openclaw/)
_BRIDGE_DIR = Path(__file__).resolve().parent.parent
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from vault_inbox_bridge import VaultInboxBridgeError, invoke_inbox_write  # noqa: E402
from vault_draft_promote_bridge import (  # noqa: E402
    VaultDraftPromoteBridgeError,
    invoke_draft_promote,
    list_promotable_notes,
)
from vault_report_promote_bridge import (  # noqa: E402
    VaultReportPromoteBridgeError,
    invoke_report_promote,
)


class ActionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BaseAction:
    action_id = ""

    def __init__(self, policy: PolicyStore):
        self.policy = policy

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        raise NotImplementedError

    @staticmethod
    def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ActionError("invalid_params", f"{field_name} must be an object")
        return value

    @staticmethod
    def _require_string(value: Any, field_name: str, *, max_len: int = 256) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ActionError("invalid_params", f"{field_name} must be a non-empty string")
        if len(value) > max_len:
            raise ActionError("invalid_params", f"{field_name} exceeds max length")
        return value

    @staticmethod
    def _optional_int(value: Any, field_name: str, *, minimum: int, maximum: int) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int):
            raise ActionError("invalid_params", f"{field_name} must be an integer")
        if value < minimum or value > maximum:
            raise ActionError("invalid_params", f"{field_name} out of allowed range")
        return value


class HealthAction(BaseAction):
    action_id = "action.health.general.v1"

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        if params:
            raise ActionError("invalid_params", "health action does not accept params")
        statuses = {}
        for check_id, check in self.policy.health_checks.items():
            request = urllib.request.Request(check.url, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    body = response.read(512).decode("utf-8", "replace")
                    statuses[check_id] = {
                        "ok": response.status == check.expect_status,
                        "status": response.status,
                        "expect_status": check.expect_status,
                        "body_preview": body[:120],
                    }
            except Exception as exc:
                statuses[check_id] = {
                    "ok": False,
                    "status": "unreachable",
                    "expect_status": check.expect_status,
                    "error": str(exc),
                }
        overall_ok = all(item["ok"] for item in statuses.values()) if statuses else True
        return BrokerResult(
            ok=overall_ok,
            action_id=self.action_id,
            result={"checks": statuses},
            audit_params={},
        )


class LogsAction(BaseAction):
    action_id = "action.logs.read.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "stream_id": params.get("stream_id"),
            "tail_lines": params.get("tail_lines"),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        stream_id = self._require_string(params.get("stream_id"), "stream_id", max_len=64)
        tail_lines = self._optional_int(
            params.get("tail_lines"),
            "tail_lines",
            minimum=1,
            maximum=self.policy.broker.max_tail_lines,
        )
        stream = self.policy.log_streams.get(stream_id)
        if stream is None:
            raise ActionError("forbidden", "stream_id is not allowed")
        lines_to_read = tail_lines or stream.tail_lines_default
        path = Path(stream.path)
        if not path.is_file():
            raise ActionError("not_found", "allowed log stream path does not exist")
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = list(deque(handle, maxlen=lines_to_read))
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "stream_id": stream_id,
                "path": str(path),
                "tail_lines": lines_to_read,
                "lines": [line.rstrip("\n") for line in lines],
            },
            audit_params=self.audit_params({"stream_id": stream_id, "tail_lines": lines_to_read}),
        )


class WebhookAction(BaseAction):
    action_id = "action.webhook.trigger.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_id": params.get("target_id"),
            "event_type": params.get("event_type"),
            "note": params.get("note"),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        target_id = self._require_string(params.get("target_id"), "target_id", max_len=64)
        event_type = self._require_string(params.get("event_type"), "event_type", max_len=64)
        note = self._require_string(params.get("note"), "note", max_len=240)
        target = self.policy.webhook_targets.get(target_id)
        if target is None:
            raise ActionError("forbidden", "target_id is not allowed")
        body = json.dumps(
            {
                "action_id": self.action_id,
                "target_id": target_id,
                "event_type": event_type,
                "note": note,
            }
        ).encode("utf-8")
        request = urllib.request.Request(target.url, data=body, method=target.method)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=target.timeout_seconds) as response:
                response_body = response.read(512).decode("utf-8", "replace")
                return BrokerResult(
                    ok=200 <= response.status < 300,
                    action_id=self.action_id,
                    result={
                        "target_id": target_id,
                        "status": response.status,
                        "response_preview": response_body[:120],
                    },
                    audit_params=self.audit_params(
                        {"target_id": target_id, "event_type": event_type, "note": note}
                    ),
                )
        except urllib.error.HTTPError as exc:
            raise ActionError("upstream_http_error", f"webhook returned {exc.code}") from exc
        except Exception as exc:
            raise ActionError("upstream_unreachable", str(exc)) from exc


class RestartOpenClawAction(BaseAction):
    action_id = "action.openclaw.restart.v1"

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        if params:
            raise ActionError("invalid_params", "restart action does not accept params")
        return BrokerResult(
            ok=False,
            action_id=self.action_id,
            error="restart not enabled in broker MVP",
            code="not_implemented",
            result={
                "reason": "requires dedicated root-owned wrapper or scoped sudo policy",
            },
            audit_params={},
        )


class DropzoneWriteAction(BaseAction):
    action_id = "action.dropzone.write.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        content = params.get("content", "")
        return {
            "filename": params.get("filename"),
            "content_bytes": len(content.encode("utf-8")) if isinstance(content, str) else 0,
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        filename = self._require_string(params.get("filename"), "filename", max_len=128)
        content = self._require_string(params.get("content"), "content", max_len=self.policy.broker.max_write_bytes)
        if "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise ActionError("invalid_params", "filename must be a basename without traversal")
        destination_root = Path(self.policy.broker.dropzone_dir).resolve()
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = (destination_root / filename).resolve()
        if destination.parent != destination_root:
            raise ActionError("invalid_params", "resolved path escapes dropzone")
        raw = content.encode("utf-8")
        if len(raw) > self.policy.broker.max_write_bytes:
            raise ActionError("invalid_params", "content exceeds configured max_write_bytes")
        destination.write_bytes(raw)
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "filename": filename,
                "path": str(destination),
                "bytes_written": len(raw),
            },
            audit_params=self.audit_params({"filename": filename, "content": content}),
        )


class InboxWriteAction(BaseAction):
    action_id = "action.inbox.write.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        body = params.get("capture_body", "")
        return {
            "run_id": params.get("run_id"),
            "capture_title": params.get("capture_title"),
            "body_bytes": len(body.encode("utf-8")) if isinstance(body, str) else 0,
            "source_refs_count": len(params.get("source_refs") or []),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_inbox.vault_root is not configured in policy")
        run_id = self._require_string(params.get("run_id"), "run_id", max_len=64)
        capture_title = self._require_string(params.get("capture_title"), "capture_title", max_len=160)
        capture_body = self._require_string(
            params.get("capture_body"), "capture_body", max_len=self.policy.broker.max_write_bytes
        )
        source_refs = params.get("source_refs")
        if source_refs is not None and not isinstance(source_refs, list):
            raise ActionError("invalid_params", "source_refs must be a list or null")
        try:
            result = invoke_inbox_write(
                vault_root=vault_root,
                run_id=run_id,
                capture_title=capture_title,
                capture_body=capture_body,
                source_refs=source_refs,
            )
        except VaultInboxBridgeError as exc:
            raise ActionError(exc.code, exc.message) from exc
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result=result,
            audit_params=self.audit_params(
                {
                    "run_id": run_id,
                    "capture_title": capture_title,
                    "capture_body": capture_body,
                    "source_refs": source_refs,
                }
            ),
        )


class DraftPromoteAction(BaseAction):
    action_id = "action.draft.promote.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "note_name": params.get("note_name"),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_inbox.vault_root is not configured in policy")
        note_name = self._require_string(params.get("note_name"), "note_name", max_len=256)
        try:
            result = invoke_draft_promote(
                vault_root=vault_root,
                note_name=note_name,
            )
        except VaultDraftPromoteBridgeError as exc:
            raise ActionError(exc.code, exc.message) from exc
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result=result,
            audit_params=self.audit_params({"note_name": note_name}),
        )


class ReportPromoteAction(BaseAction):
    action_id = "action.report.promote.v1"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "note_name": params.get("note_name"),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_inbox.vault_root is not configured in policy")
        note_name = self._require_string(params.get("note_name"), "note_name", max_len=256)
        try:
            result = invoke_report_promote(
                vault_root=vault_root,
                note_name=note_name,
            )
        except VaultReportPromoteBridgeError as exc:
            raise ActionError(exc.code, exc.message) from exc
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result=result,
            audit_params=self.audit_params({"note_name": note_name}),
        )


class NoteCreateAction(BaseAction):
    """E3 — Create a note in any non-reserved vault folder."""

    action_id = "action.note.create.v1"
    _EXCLUDED_FOLDERS: frozenset[str] = frozenset({"Agent", "Agent/Inbox_Agent", ".obsidian", ".git"})
    _SLUG_RE = re.compile(r"[^\w\-]")

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        body = params.get("body", "")
        return {
            "folder": params.get("folder"),
            "title": params.get("title"),
            "body_bytes": len(body.encode("utf-8")) if isinstance(body, str) else 0,
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_root is not configured in policy")
        folder = self._require_string(params.get("folder"), "folder", max_len=128)
        title = self._require_string(params.get("title"), "title", max_len=160)
        body = self._require_string(params.get("body"), "body", max_len=self.policy.broker.max_write_bytes)

        if folder in self._EXCLUDED_FOLDERS or folder.startswith("Agent"):
            raise ActionError("forbidden", "folder is reserved for pipeline use")
        if ".." in folder or folder.startswith("/"):
            raise ActionError("invalid_params", "folder must be a relative path without traversal")

        root = Path(vault_root).resolve()
        target_dir = (root / folder).resolve()
        if not str(target_dir).startswith(str(root)):
            raise ActionError("invalid_params", "folder resolves outside vault")
        if not target_dir.is_dir():
            raise ActionError("not_found", f"folder '{folder}' does not exist in vault")

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "Z"
        slug = self._SLUG_RE.sub("_", title.lower())[:40].strip("_")
        filename = f"{ts}_{slug}.md"
        note_path = target_dir / filename
        if note_path.exists():
            raise ActionError("conflict", "note already exists (timestamp collision)")

        created_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        content = (
            "---\n"
            f'title: "{title}"\n'
            f'created_at_utc: "{created_ts}"\n'
            f'folder: "{folder}"\n'
            "---\n\n"
            f"# {title}\n\n"
            f"{body}\n"
        )
        note_path.write_text(content, encoding="utf-8")
        try:
            rel_path = str(note_path.relative_to(root))
        except ValueError:
            rel_path = f"{folder}/{filename}"
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={"note_name": filename, "folder": folder, "path": rel_path},
            audit_params=self.audit_params({"folder": folder, "title": title, "body": body}),
        )


class NoteArchiveAction(BaseAction):
    """E4 — Move a note to the archive folder (non-destructive)."""

    action_id = "action.note.archive.v1"
    DEFAULT_ARCHIVE_FOLDER = "50_Archivado"

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "note_path": params.get("note_path"),
            "destination_folder": params.get("destination_folder", self.DEFAULT_ARCHIVE_FOLDER),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_root is not configured in policy")
        note_path_str = self._require_string(params.get("note_path"), "note_path", max_len=512)
        destination_folder = params.get("destination_folder") or self.DEFAULT_ARCHIVE_FOLDER

        if ".." in note_path_str or note_path_str.startswith("/"):
            raise ActionError("invalid_params", "note_path must be relative without traversal")
        if isinstance(destination_folder, str) and (".." in destination_folder or destination_folder.startswith("/")):
            raise ActionError("invalid_params", "destination_folder must be relative without traversal")

        root = Path(vault_root).resolve()
        source = (root / note_path_str).resolve()
        if not str(source).startswith(str(root)):
            raise ActionError("invalid_params", "note_path resolves outside vault")
        if not source.is_file():
            raise ActionError("not_found", f"note not found: {note_path_str}")

        dest_dir = (root / str(destination_folder)).resolve()
        if not str(dest_dir).startswith(str(root)):
            raise ActionError("invalid_params", "destination resolves outside vault")
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / source.name
        if dest_path.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest_path = dest_dir / f"{source.stem}_{ts}{source.suffix}"

        source.rename(dest_path)
        try:
            from_rel = str(source.relative_to(root))
            to_rel = str(dest_path.relative_to(root))
        except ValueError:
            from_rel = note_path_str
            to_rel = f"{destination_folder}/{dest_path.name}"
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "note_name": source.name,
                "from_path": from_rel,
                "to_path": to_rel,
                "destination_folder": str(destination_folder),
            },
            audit_params=self.audit_params({"note_path": note_path_str, "destination_folder": destination_folder}),
        )


class NoteEditAction(BaseAction):
    """E5 — Append text to or fully replace the content of an existing vault note."""

    action_id = "action.note.edit.v1"
    _EXCLUDED_FOLDERS: frozenset[str] = frozenset({"Agent", ".obsidian", ".git"})
    _ALLOWED_MODES: frozenset[str] = frozenset({"append", "replace"})

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        content = params.get("content", "")
        return {
            "note_path": params.get("note_path"),
            "mode": params.get("mode"),
            "content_bytes": len(content.encode("utf-8")) if isinstance(content, str) else 0,
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_root is not configured in policy")
        note_path_str = self._require_string(params.get("note_path"), "note_path", max_len=512)
        mode = self._require_string(params.get("mode"), "mode", max_len=16)
        content = self._require_string(
            params.get("content"), "content",
            max_len=self.policy.broker.max_write_bytes,
        )

        if mode not in self._ALLOWED_MODES:
            raise ActionError("invalid_params", f"mode must be one of: {', '.join(sorted(self._ALLOWED_MODES))}")
        if ".." in note_path_str or note_path_str.startswith("/"):
            raise ActionError("invalid_params", "note_path must be relative without traversal")

        root = Path(vault_root).resolve()
        note_path = (root / note_path_str).resolve()
        if not str(note_path).startswith(str(root)):
            raise ActionError("invalid_params", "note_path resolves outside vault")
        if not note_path.is_file():
            raise ActionError("not_found", f"note not found: {note_path_str}")

        # Block edits to reserved folders
        try:
            parts = note_path.relative_to(root).parts
        except ValueError:
            parts = ()
        if parts and parts[0] in self._EXCLUDED_FOLDERS:
            raise ActionError("forbidden", "editing notes in reserved folders is not allowed")

        if mode == "append":
            existing = note_path.read_text(encoding="utf-8")
            new_content = existing.rstrip("\n") + "\n\n" + content + "\n"
        else:  # replace
            new_content = content if content.endswith("\n") else content + "\n"

        bytes_written = len(new_content.encode("utf-8"))
        note_path.write_text(new_content, encoding="utf-8")
        try:
            rel_path = str(note_path.relative_to(root))
        except ValueError:
            rel_path = note_path_str
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "note_name": note_path.name,
                "rel_path": rel_path,
                "mode": mode,
                "bytes_written": bytes_written,
            },
            audit_params=self.audit_params({"note_path": note_path_str, "mode": mode, "content": content}),
        )


class NoteMoveFolderAction(BaseAction):
    """E6 — Move a note to a different vault folder (not archive-specific)."""

    action_id = "action.note.move.v1"
    _EXCLUDED_FOLDERS: frozenset[str] = frozenset({"Agent", "Agent/Inbox_Agent", ".obsidian", ".git"})

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "note_path": params.get("note_path"),
            "dest_folder": params.get("dest_folder"),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_root is not configured in policy")
        note_path_str = self._require_string(params.get("note_path"), "note_path", max_len=512)
        dest_folder = self._require_string(params.get("dest_folder"), "dest_folder", max_len=128)

        if ".." in note_path_str or note_path_str.startswith("/"):
            raise ActionError("invalid_params", "note_path must be relative without traversal")
        if ".." in dest_folder or dest_folder.startswith("/"):
            raise ActionError("invalid_params", "dest_folder must be relative without traversal")
        if dest_folder in self._EXCLUDED_FOLDERS or dest_folder.startswith("Agent"):
            raise ActionError("forbidden", "destination folder is reserved for pipeline use")

        root = Path(vault_root).resolve()
        source = (root / note_path_str).resolve()
        if not str(source).startswith(str(root)):
            raise ActionError("invalid_params", "note_path resolves outside vault")
        if not source.is_file():
            raise ActionError("not_found", f"note not found: {note_path_str}")

        dest_dir = (root / dest_folder).resolve()
        if not str(dest_dir).startswith(str(root)):
            raise ActionError("invalid_params", "dest_folder resolves outside vault")
        if not dest_dir.is_dir():
            raise ActionError("not_found", f"destination folder '{dest_folder}' does not exist in vault")

        # Check source is not in a reserved folder
        try:
            src_parts = source.relative_to(root).parts
        except ValueError:
            src_parts = ()
        if src_parts and src_parts[0] in {"Agent", ".obsidian", ".git"}:
            raise ActionError("forbidden", "moving notes from reserved folders is not allowed")

        dest_path = dest_dir / source.name
        if dest_path.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest_path = dest_dir / f"{source.stem}_{ts}{source.suffix}"

        source.rename(dest_path)
        try:
            from_rel = str(source.relative_to(root))
            to_rel = str(dest_path.relative_to(root))
        except ValueError:
            from_rel = note_path_str
            to_rel = f"{dest_folder}/{dest_path.name}"
        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "note_name": source.name,
                "from_path": from_rel,
                "to_path": to_rel,
                "dest_folder": dest_folder,
            },
            audit_params=self.audit_params({"note_path": note_path_str, "dest_folder": dest_folder}),
        )


class HeartbeatWriteAction(BaseAction):
    """Write a create-only heartbeat note to Agent/Heartbeat/.

    Connects openclaw bot with the heartbeat.write contract defined in
    obsi-claw-AI_agent/scripts/helpers/openclaw_vault_heartbeat_writer.py.
    """

    action_id = "action.heartbeat.write.v1"
    _HEARTBEAT_DIR = Path("Agent") / "Heartbeat"
    _SLUG_RE = re.compile(r"[^\w\-]")

    def audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "heartbeat_type": params.get("heartbeat_type", "runtime-status"),
            "context_len": len(str(params.get("context", ""))),
        }

    def execute(self, params: dict[str, Any]) -> BrokerResult:
        vault_root = self.policy.vault_inbox.vault_root
        if not vault_root:
            raise ActionError("not_configured", "vault_root is not configured in policy")

        heartbeat_type = str(params.get("heartbeat_type") or "runtime-status").strip()
        context = self._require_string(params.get("context"), "context", max_len=2048)
        result_text = str(params.get("result") or "Heartbeat manual desde Telegram.").strip()

        root = Path(vault_root).resolve()
        heartbeat_dir = (root / self._HEARTBEAT_DIR).resolve()
        if not str(heartbeat_dir).startswith(str(root)):
            raise ActionError("invalid_params", "heartbeat dir resolves outside vault")
        if not heartbeat_dir.is_dir():
            try:
                heartbeat_dir.mkdir(parents=False, mode=0o750)
            except Exception as exc:
                raise ActionError("not_found", f"Agent/Heartbeat does not exist: {exc}") from exc

        now = datetime.now(timezone.utc)
        ts_file = now.strftime("%Y%m%dT%H%M%SZ")
        ts_front = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        run_id = ts_file
        filename = f"{ts_file}_{heartbeat_type}_{run_id}.md"
        note_path = heartbeat_dir / filename
        if note_path.exists():
            raise ActionError("conflict", "heartbeat note already exists (timestamp collision)")

        content = (
            "---\n"
            "managed_by: openclaw\n"
            "agent_zone: Heartbeat\n"
            f'run_id: "{run_id}"\n'
            f'created_at_utc: "{ts_front}"\n'
            f'updated_at_utc: "{ts_front}"\n'
            "source_refs: []\n"
            "human_review_status: not_required\n"
            f'heartbeat_type: "{heartbeat_type}"\n'
            "---\n\n"
            f"# Heartbeat {heartbeat_type}\n\n"
            "## Contexto\n\n"
            f"{context.strip()}\n\n"
            "## Resultado\n\n"
            f"{result_text.strip()}\n\n"
            "## Trazabilidad\n\n"
            f"- operation: `heartbeat.write`\n"
            f"- run_id: `{run_id}`\n"
            f"- heartbeat_type: `{heartbeat_type}`\n"
            f"- created_at_utc: `{ts_front}`\n"
        )
        try:
            note_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ActionError("io_error", f"failed to write heartbeat: {exc}") from exc

        try:
            rel_path = str(note_path.relative_to(root))
        except ValueError:
            rel_path = str(self._HEARTBEAT_DIR / filename)

        return BrokerResult(
            ok=True,
            action_id=self.action_id,
            result={
                "note_name": filename,
                "rel_path": rel_path,
                "heartbeat_type": heartbeat_type,
                "run_id": run_id,
            },
            audit_params=self.audit_params(params),
        )


def build_action_registry(policy: PolicyStore) -> dict[str, BaseAction]:
    actions: list[BaseAction] = [
        HealthAction(policy),
        LogsAction(policy),
        WebhookAction(policy),
        RestartOpenClawAction(policy),
        DropzoneWriteAction(policy),
        InboxWriteAction(policy),
        DraftPromoteAction(policy),
        ReportPromoteAction(policy),
        NoteCreateAction(policy),
        NoteArchiveAction(policy),
        NoteEditAction(policy),
        NoteMoveFolderAction(policy),
        HeartbeatWriteAction(policy),
    ]
    return {action.action_id: action for action in actions}
