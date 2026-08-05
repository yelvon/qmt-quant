"""Tests for kline payload builder."""

import pytest

from qmt_quant.core.data.kline import build_kline_payload
from qmt_quant.storage.bars import BarRow, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "kline.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    with db_session(db_file) as conn:
        upsert_bars(
            conn,
            [
                BarRow(
                    code="600519.SH",
                    date="2024-01-02",
                    adjust_type="front",
                    open=100,
                    high=105,
                    low=99,
                    close=104,
                    volume=1000,
                    amount=104000,
                ),
                BarRow(
                    code="600519.SH",
                    date="2024-01-03",
                    adjust_type="front",
                    open=104,
                    high=106,
                    low=103,
                    close=105,
                    volume=900,
                    amount=94500,
                ),
            ],
        )
    yield db_file
    config._settings = None


def test_kline_payload_format(db):
    with db_session(db) as conn:
        payload = build_kline_payload(
            conn,
            "600519.SH",
            date_from="2024-01-02",
            date_to="2024-01-03",
            adjust="front",
        )
    assert payload["ok"] is True
    assert payload["code"] == "600519.SH"
    assert payload["empty"] is False
    assert payload["dates"] == ["2024-01-02", "2024-01-03"]
    assert payload["ohlc"][0] == [100, 104, 99, 105]
    assert payload["volume"] == [1000, 900]


def test_kline_empty_hint(db):
    with db_session(db) as conn:
        payload = build_kline_payload(conn, "999999.SH", adjust="front")
    assert payload["empty"] is True
    assert "hint" in payload
    assert payload["ohlc"] == []


def test_kline_missing_code(db):
    with db_session(db) as conn:
        with pytest.raises(ValueError, match="missing_code"):
            build_kline_payload(conn, "", adjust="front")
