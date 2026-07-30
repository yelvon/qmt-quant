"""Trade calendar sync from bar dates."""

from __future__ import annotations

from typing import List

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


def list_trade_dates(limit: int = 5000) -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT cal_date FROM trade_calendar WHERE is_open=1 ORDER BY cal_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r[0] for r in rows]
