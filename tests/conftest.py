"""Shared PostgreSQL test fixtures."""

from __future__ import annotations

import os

import pytest

DEFAULT_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://qmt:qmt@localhost:5432/qmt_quant",
)


def _truncate_all(database_url: str) -> None:
    from qmt_quant.storage.database import db_session

    tables = [
        "screening_result",
        "live_order",
        "backtest_run",
        "job",
        "sync_batch",
        "financial_balance",
        "financial_income",
        "financial_cashflow",
        "financial_pershareindex",
        "daily_bar",
        "index_daily_bar",
        "index_instrument",
        "instrument",
        "trade_calendar",
        "sync_meta",
    ]
    with db_session(database_url) as conn:
        conn.execute(
            "TRUNCATE TABLE "
            + ", ".join(tables)
            + " RESTART IDENTITY CASCADE"
        )
    try:
        from qmt_quant.core.data.query import clear_browse_query_cache

        clear_browse_query_cache()
    except Exception:
        pass


@pytest.fixture(scope="session")
def database_url() -> str:
    return DEFAULT_TEST_DATABASE_URL


@pytest.fixture
def db(monkeypatch, database_url: str):
    """Fresh schema on PostgreSQL test database."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    from qmt_quant import config

    config._settings = None
    from qmt_quant.storage.database import ping_database, run_migrations

    ok, msg = ping_database(database_url)
    if not ok:
        pytest.skip(msg)
    run_migrations(database_url)
    _truncate_all(database_url)
    yield database_url
    config._settings = None


@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient

    from qmt_quant.web.app import create_app

    app = create_app()
    yield TestClient(app)
