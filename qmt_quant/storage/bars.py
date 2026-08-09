"""Bar repository."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


@dataclass
class BarRow:
    code: str
    date: str
    adjust_type: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    pre_close: Optional[float] = None
    turnover: Optional[float] = None
    quality_status: str = "ok"


UPSERT_BAR_SQL = """
INSERT INTO daily_bar (
    code, date, adjust_type, open, high, low, close, volume, amount,
    pre_close, turnover, quality_status, source, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'qmt', datetime('now'))
ON CONFLICT(code, date, adjust_type) DO UPDATE SET
    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
    volume=excluded.volume, amount=excluded.amount, pre_close=excluded.pre_close,
    turnover=excluded.turnover, quality_status=excluded.quality_status,
    updated_at=datetime('now')
"""


def upsert_bars(conn: sqlite3.Connection, rows: Iterable[BarRow]) -> int:
    data = [
        (
            r.code, r.date, r.adjust_type, r.open, r.high, r.low, r.close,
            r.volume, r.amount, r.pre_close, r.turnover, r.quality_status,
        )
        for r in rows
    ]
    if not data:
        return 0
    conn.executemany(UPSERT_BAR_SQL, data)
    return len(data)


def load_bars_df(
    conn: sqlite3.Connection,
    codes: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust_type: str = "front",
) -> pd.DataFrame:
    clauses = ["adjust_type = ?"]
    params: List = [adjust_type]
    if codes:
        placeholders = ",".join("?" * len(codes))
        clauses.append(f"code IN ({placeholders})")
        params.extend(codes)
    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    where = " AND ".join(clauses)
    sql = f"SELECT * FROM daily_bar WHERE {where} ORDER BY date, code"
    df = pd.read_sql_query(sql, conn, params=params)
    return df


def quality_stats(conn: sqlite3.Connection, adjust_type: str = "front") -> Dict[str, object]:
    rows = conn.execute(
        """
        SELECT quality_status, COUNT(*) AS cnt
        FROM daily_bar WHERE adjust_type = ?
        GROUP BY quality_status
        """,
        (adjust_type,),
    ).fetchall()
    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values()) or 1
    bad = counts.get("bad", 0)
    suspicious = counts.get("suspicious", 0)
    return {
        "bad_bars_count": bad,
        "suspicious_bars_count": suspicious,
        "suspicious_pct": round((bad + suspicious) / total * 100, 2),
        "by_status": counts,
    }


def coverage_stats(conn: sqlite3.Connection, adjust_type: str = "front") -> Dict[str, object]:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT code) AS codes,
               COUNT(*) AS rows,
               MIN(date) AS min_date,
               MAX(date) AS max_date
        FROM daily_bar WHERE adjust_type = ?
        """,
        (adjust_type,),
    ).fetchone()
    return dict(row) if row else {}


def market_latest_date(conn: sqlite3.Connection, adjust_type: str = "front") -> Optional[str]:
    row = conn.execute(
        "SELECT MAX(date) FROM daily_bar WHERE adjust_type = ?",
        (adjust_type,),
    ).fetchone()
    return row[0] if row and row[0] else None


def latest_bar_dates(conn: sqlite3.Connection, adjust_type: str = "front") -> Dict[str, str]:
    rows = conn.execute(
        """
        SELECT code, MAX(date) AS latest
        FROM daily_bar WHERE adjust_type = ?
        GROUP BY code
        """,
        (adjust_type,),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def bar_counts_by_code(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    adjust_type: str = "front",
    codes: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    clauses = ["adjust_type = ?", "date >= ?", "date <= ?"]
    params: List = [adjust_type, start, end]
    if codes:
        placeholders = ",".join("?" * len(codes))
        clauses.append(f"code IN ({placeholders})")
        params.extend(codes)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT code, COUNT(*) AS cnt
        FROM daily_bar WHERE {where}
        GROUP BY code
        """,
        params,
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def index_bar_dates(
    conn: sqlite3.Connection,
    code: str = "000001.SH",
    adjust_type: str = "front",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[str]:
    clauses = ["code = ?", "adjust_type = ?"]
    params: List = [code, adjust_type]
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT date FROM daily_bar WHERE {where} ORDER BY date",
        params,
    ).fetchall()
    return [r[0] for r in rows]
