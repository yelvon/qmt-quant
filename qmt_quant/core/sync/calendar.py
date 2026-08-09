"""Trade calendar sync."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.storage.database import db_session, run_migrations


def sync_calendar_from_bars() -> int:
    """Populate trade_calendar from distinct daily_bar dates."""
    run_migrations()
    with db_session() as conn:
        rows = conn.execute("SELECT DISTINCT date FROM daily_bar ORDER BY date").fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO trade_calendar(cal_date, is_open) VALUES (?, 1)
                ON CONFLICT(cal_date) DO NOTHING
                """,
                (row[0],),
            )
    return len(rows)


def sync_calendar_from_qmt(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    market: str = "SH",
) -> int:
    """Sync trade_calendar from QMT trading dates (fallback: index bars)."""
    run_migrations()
    end = end_date or date.today().isoformat()
    start = start_date or resolve_range_preset("3y", max_date=end)[0]
    from qmt_quant.adapters.qmt.client import XtDataClient

    client = XtDataClient()
    dates = client.get_trading_dates(market=market, start_date=start, end_date=end)
    with db_session() as conn:
        for d in dates:
            conn.execute(
                """
                INSERT INTO trade_calendar(cal_date, is_open) VALUES (?, 1)
                ON CONFLICT(cal_date) DO UPDATE SET is_open = 1
                """,
                (d,),
            )
    return len(dates)


def list_trade_dates(limit: int = 5000) -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT cal_date FROM trade_calendar WHERE is_open=1 ORDER BY cal_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r[0] for r in rows]


def list_trade_dates_between(start: str, end: str) -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT cal_date FROM trade_calendar
            WHERE is_open = 1 AND cal_date >= ? AND cal_date <= ?
            ORDER BY cal_date
            """,
            (start, end),
        ).fetchall()
    return [r[0] for r in rows]
