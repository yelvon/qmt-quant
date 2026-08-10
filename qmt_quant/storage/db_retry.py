"""SQLite write retry helper."""

from __future__ import annotations

import sqlite3
import time
from typing import Callable, TypeVar

T = TypeVar("T")

_MAX_ATTEMPTS = 8


def is_db_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()


def run_db_retry(action: Callable[[], T], *, attempts: int = _MAX_ATTEMPTS) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return action()
        except sqlite3.OperationalError as exc:
            last = exc
            if not is_db_locked_error(exc) or attempt == attempts - 1:
                raise
            time.sleep(0.15 * (attempt + 1))
    raise last  # pragma: no cover
