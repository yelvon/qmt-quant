"""PostgreSQL transient error retry tests."""

import psycopg
import pytest

from qmt_quant.storage.db_retry import is_transient_db_error, run_db_retry


def test_transient_deadlock_detected():
    assert is_transient_db_error(psycopg.errors.DeadlockDetected("deadlock"))


def test_non_transient_error():
    assert not is_transient_db_error(ValueError("nope"))


def test_run_db_retry_eventually_succeeds():
    calls = {"n": 0}

    def action():
        calls["n"] += 1
        if calls["n"] < 2:
            raise psycopg.errors.DeadlockDetected("deadlock")
        return "ok"

    assert run_db_retry(action, attempts=3) == "ok"
