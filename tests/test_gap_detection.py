"""Gap detection and repair plan tests."""

from datetime import date, timedelta

import pytest

from qmt_quant.core.sync.gaps import analyze_gaps, build_repair_plan
from qmt_quant.storage.bars import BarRow, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations


def _seed_calendar(conn, dates):
    for d in dates:
        conn.execute(
            "INSERT INTO trade_calendar(cal_date, is_open) VALUES (?, 1) ON CONFLICT DO NOTHING",
            (d,),
        )


def _seed_instruments(conn, codes):
    for code in codes:
        conn.execute(
            """
            INSERT INTO instrument(code, name) VALUES (?, ?)
            ON CONFLICT(code) DO NOTHING
            """,
            (code, code),
        )


@pytest.fixture
def gap_db(tmp_path, monkeypatch):
    db_file = tmp_path / "gaps.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)

    today = date.today()
    trade_dates = [(today - timedelta(days=i)).isoformat() for i in range(10, 0, -1)]

    with db_session(db_file) as conn:
        _seed_calendar(conn, trade_dates)
        codes = ["600519.SH", "000001.SZ", "600000.SH"]
        _seed_instruments(conn, codes)
        latest = trade_dates[-1]
        stale_latest = trade_dates[-5]
        for code in codes:
            bar_date = stale_latest if code == "600000.SH" else latest
            upsert_bars(
                conn,
                [
                    BarRow(
                        code=code,
                        date=bar_date,
                        adjust_type="front",
                        open=10,
                        high=11,
                        low=9,
                        close=10,
                        volume=100,
                        amount=1000,
                    )
                ],
            )
        upsert_bars(
            conn,
            [
                BarRow(
                    code="000001.SH",
                    date=latest,
                    adjust_type="front",
                    open=3000,
                    high=3010,
                    low=2990,
                    close=3005,
                    volume=1e6,
                    amount=1e9,
                )
            ],
        )
    yield db_file
    config._settings = None


def test_detects_stale_code(gap_db):
    result = analyze_gaps(adjust_type="front", detailed=True)
    assert "600000.SH" in result["stale_codes"]
    assert result["needs_repair"] is True
    plan = result["repair_plan"]
    assert "600000.SH" in plan["codes"]


def test_build_repair_plan_for_codes(gap_db):
    plan = build_repair_plan(codes=["600000.SH"], adjust_type="front")
    assert plan.codes == ["600000.SH"]
    assert plan.date_ranges
    assert plan.date_ranges[0]["end"]
