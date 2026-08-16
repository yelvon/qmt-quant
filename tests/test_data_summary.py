"""Tests for lightweight data summary."""

from __future__ import annotations

from qmt_quant.core.sync.check import run_data_summary
from qmt_quant.storage.bars import BarRow, upsert_bars
from qmt_quant.storage.database import db_session


def test_run_data_summary(db):
    with db_session(db) as conn:
        upsert_bars(
            conn,
            [
                BarRow(
                    code="600519.SH",
                    date="2024-01-02",
                    adjust_type="front",
                    open=1,
                    high=2,
                    low=1,
                    close=1.5,
                    volume=1,
                    amount=1,
                )
            ],
        )

    summary = run_data_summary(adjust_type="front", use_cache=False)
    assert summary["bar_date_min"] == "2024-01-02"
    assert summary["bar_date_max"] == "2024-01-02"
    assert summary["bar_codes_count"] == 1
    assert "financial_row_count" in summary
