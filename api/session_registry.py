from __future__ import annotations

import time
from typing import Any, Callable


class SessionRegistry(dict):
    """Dict-compatible session store with max-size and idle-TTL eviction.

    Eviction runs on every write; reads refresh the entry's last-access time.
    """

    def __init__(
        self,
        max_sessions: int = 500,
        ttl_seconds: int = 3600,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._now = now_fn
        self._last_access: dict[Any, float] = {}
        self._owners: dict[Any, str | None] = {}

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._last_access[key] = self._now()
        self._evict()

    def owner(self, key: Any) -> str | None:
        if key in self:
            self._last_access[key] = self._now()
        return self._owners.get(key)

    def set_owner(self, key: Any, owner: str | None) -> None:
        if key in self:
            self._owners[key] = owner

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self:
            self._last_access[key] = self._now()
        return super().get(key, default)

    def pop(self, key: Any, default: Any = None) -> Any:
        self._last_access.pop(key, None)
        self._owners.pop(key, None)
        return super().pop(key, default)

    def clear(self) -> None:
        self._last_access.clear()
        self._owners.clear()
        super().clear()

    def _evict(self) -> None:
        now = self._now()
        expired = [key for key, seen in self._last_access.items() if now - seen > self.ttl_seconds]
        for key in expired:
            super().pop(key, None)
            self._last_access.pop(key, None)
            self._owners.pop(key, None)
        while len(self) > self.max_sessions:
            oldest_key = min(self._last_access, key=self._last_access.get)
            super().pop(oldest_key, None)
            self._last_access.pop(oldest_key, None)
            self._owners.pop(oldest_key, None)
