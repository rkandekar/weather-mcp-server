"""A minimal in-memory TTL cache to avoid hammering the upstream weather APIs."""
from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """A single-process cache that expires entries after a fixed time-to-live.

    Deliberately simple: an MCP stdio server runs as one process per client
    session, so there is no need for a shared/distributed cache such as Redis.
    Not thread-safe, but the server's async tool handlers run on a single
    event loop so this is not a concern here.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        """Return the cached value for `key`, or None if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        """Store `value` under `key`, expiring it after the configured TTL."""
        self._store[key] = (time.monotonic() + self._ttl_seconds, value)

    def clear(self) -> None:
        """Remove all cached entries."""
        self._store.clear()
