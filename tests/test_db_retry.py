"""DB retry helper tests."""

import sqlite3
from unittest.mock import MagicMock

import pytest

from qmt_quant.storage.db_retry import is_db_locked_error, run_db_retry


def test_is_db_locked_error():
    assert is_db_locked_error(sqlite3.OperationalError("database is locked"))
    assert not is_db_locked_error(sqlite3.OperationalError("no such table"))


def test_run_db_retry_recovers(monkeypatch):
    calls = {"n": 0}

    def action() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    monkeypatch.setattr("qmt_quant.storage.db_retry.time.sleep", lambda *_: None)
    assert run_db_retry(action, attempts=5) == "ok"
    assert calls["n"] == 3
