"""PE momentum research tests."""

import json

import pandas as pd
import pytest

from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import upsert_financial


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    yield db_file
    config._settings = None


def test_pe_momentum_no_future_leak(db, monkeypatch):
    monkeypatch.setenv("QMT_QUANT_DB", str(db))
    from qmt_quant import config

    config._settings = None
    with db_session(db) as conn:
        upsert_financial(
            conn,
            "Pershareindex",
            "600519.SH",
            "2023-12-31",
            "2024-04-30",
            {"pe_ttm": 20.0, "roe": 0.15},
        )
    from qmt_quant.core.research.factors import load_pe_matrix

    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    with db_session(db) as conn:
        pe = load_pe_matrix(conn, dates, ["600519.SH"])
    assert pe.loc[dates[10], "600519.SH"] != pe.loc[dates[-1], "600519.SH"] or pd.isna(
        pe.loc[dates[10], "600519.SH"]
    )
