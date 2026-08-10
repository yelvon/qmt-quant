"""Lightweight in-process TTL cache for hot API paths."""

from __future__ import annotations

import time
from typing import Callable, Dict, Generic, Hashable, Optional, Tuple, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: Dict[Hashable, Tuple[float, T]] = {}

    def get(self, key: Hashable) -> Optional[T]:
        hit = self._entries.get(key)
        if not hit:
            return None
        expires_at, value = hit
        if time.monotonic() >= expires_at:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: T) -> None:
        self._entries[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._entries.clear()

    def get_or_set(self, key: Hashable, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value
