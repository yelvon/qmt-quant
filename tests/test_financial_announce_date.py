import json

import pytest

from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import load_financial_asof, upsert_financial


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    yield db_file
    config._settings = None


def test_financial_uses_announce_date_not_future(db):
    with db_session(db) as conn:
        upsert_financial(
            conn,
            "Pershareindex",
            "600519.SH",
            "2023-12-31",
            "2024-04-30",
            {"pe": 25.0, "roe": 0.18},
        )
        upsert_financial(
            conn,
            "Pershareindex",
            "600519.SH",
            "2024-06-30",
            "2024-08-30",
            {"pe": 30.0, "roe": 0.20},
        )
        as_of_early = load_financial_asof(conn, "Pershareindex", "600519.SH", "2024-05-01")
        as_of_late = load_financial_asof(conn, "Pershareindex", "600519.SH", "2024-09-01")
    assert as_of_early["pe"] == 25.0
    assert as_of_late["pe"] == 30.0


def test_financial_before_announce_not_visible(db):
    with db_session(db) as conn:
        upsert_financial(
            conn,
            "Pershareindex",
            "000001.SZ",
            "2024-06-30",
            "2024-08-30",
            {"pe": 12.0},
        )
        snap = load_financial_asof(conn, "Pershareindex", "000001.SZ", "2024-07-01")
    assert snap is None
