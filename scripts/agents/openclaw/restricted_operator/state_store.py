from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class StateStoreError(ValueError):
    pass


class LockedJsonStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        # The lock lives next to the JSON because os.replace swaps the target inode.
        # Locking the data file itself would not reliably serialize writers across replacements.
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def load(self) -> dict[str, Any]:
        return self._read_unlocked()

    def load_actions(self) -> dict[str, dict[str, Any]]:
        return self._extract_actions(self.load())

    def update_actions(
        self,
        mutator: Callable[[dict[str, dict[str, Any]]], None],
    ) -> dict[str, dict[str, Any]]:
        def apply(payload: dict[str, Any]) -> None:
            actions = self._extract_actions(payload)
            mutator(actions)
            payload["actions"] = actions

        payload = self.update_payload(apply)
        return self._extract_actions(payload)

    def update_payload(self, mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._exclusive_lock():
            payload = self._read_unlocked()
            mutator(payload)
            self._write_unlocked(payload)
            return payload

    @contextmanager
    def _exclusive_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            raise StateStoreError(f"invalid runtime state json: {self.path}") from exc
        if not isinstance(payload, dict):
            raise StateStoreError("runtime state payload must be an object")
        return payload

    @staticmethod
    def _extract_actions(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        actions = payload.get("actions", {})
        if not isinstance(actions, dict):
            raise StateStoreError("runtime state actions must be an object")
        return actions

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        tmp_path: Path | None = None
        existing_mode = self._existing_mode()
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_path = Path(handle.name)
                if existing_mode is not None:
                    os.fchmod(handle.fileno(), existing_mode)
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
            self._fsync_directory()
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()

    def _existing_mode(self) -> int | None:
        try:
            return self.path.stat().st_mode & 0o777
        except FileNotFoundError:
            return None

    def _fsync_directory(self) -> None:
        directory_fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
