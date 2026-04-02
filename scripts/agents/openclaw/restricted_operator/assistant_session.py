from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class AssistantSession:
    operator_id: str
    awakened_at: float
    last_activity_at: float


class AssistantSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, AssistantSession] = {}

    @staticmethod
    def session_key(*, chat_id: str, user_id: str) -> str:
        return f"{chat_id}:{user_id}"

    @staticmethod
    def now_monotonic() -> float:
        return time.monotonic()

    def wake(self, *, chat_id: str, user_id: str, operator_id: str) -> AssistantSession:
        key = self.session_key(chat_id=chat_id, user_id=user_id)
        now = self.now_monotonic()
        session = AssistantSession(
            operator_id=operator_id,
            awakened_at=now,
            last_activity_at=now,
        )
        self.sessions[key] = session
        return session

    def sleep(self, *, chat_id: str, user_id: str) -> AssistantSession | None:
        key = self.session_key(chat_id=chat_id, user_id=user_id)
        return self.sessions.pop(key, None)

    def get_active(
        self,
        *,
        chat_id: str,
        user_id: str,
        operator_id: str,
        idle_timeout_seconds: int,
        on_invalidated: Callable[[str], None] | None = None,
    ) -> AssistantSession | None:
        key = self.session_key(chat_id=chat_id, user_id=user_id)
        session = self.sessions.get(key)
        if session is None:
            return None
        if session.operator_id != operator_id:
            self.sessions.pop(key, None)
            if on_invalidated is not None:
                on_invalidated("operator_mismatch")
            return None
        now = self.now_monotonic()
        if now - session.last_activity_at > idle_timeout_seconds:
            self.sessions.pop(key, None)
            if on_invalidated is not None:
                on_invalidated("timeout")
            return None
        session.last_activity_at = now
        return session

    def has_active(self, *, chat_id: str, user_id: str, operator_id: str) -> bool:
        key = self.session_key(chat_id=chat_id, user_id=user_id)
        session = self.sessions.get(key)
        return session is not None and session.operator_id == operator_id
