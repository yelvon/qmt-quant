"""PostgreSQL transient error retry helper."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

import psycopg

T = TypeVar("T")

_MAX_ATTEMPTS = 8


def is_transient_db_error(exc: BaseException) -> bool:
    if isinstance(exc, psycopg.errors.DeadlockDetected):
        return True
    if isinstance(exc, psycopg.errors.SerializationFailure):
        return True
    if isinstance(exc, psycopg.OperationalError):
        msg = str(exc).lower()
        return "deadlock" in msg or "could not serialize" in msg or "connection" in msg
    return False


def run_db_retry(action: Callable[[], T], *, attempts: int = _MAX_ATTEMPTS) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return action()
        except Exception as exc:
            last = exc
            if not is_transient_db_error(exc) or attempt == attempts - 1:
                raise
            time.sleep(0.15 * (attempt + 1))
    raise last  # pragma: no cover
