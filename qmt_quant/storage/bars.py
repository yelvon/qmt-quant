"""Bar repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from qmt_quant.storage.database import DbConnection

UPSERT_BAR_SQL = """
INSERT INTO daily_bar (
    code, date, adjust_type, open, high, low, close, volume, amount,
    pre_close, turnover, quality_status, source, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'qmt', NOW())
ON CONFLICT(code, date, adjust_type) DO UPDATE SET
    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
    volume=EXCLUDED.volume, amount=EXCLUDED.amount, pre_close=EXCLUDED.pre_close,
    turnover=EXCLUDED.turnover, quality_status=EXCLUDED.quality_status,
    updated_at=NOW()
"""


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


def upsert_bars(conn: DbConnection, rows: Iterable[BarRow]) -> int:
    data = [
        (
            r.code, r.date, r.adjust_type, r.open, r.high, r.low, r.close,
            r.volume, r.amount, r.pre_close, r.turnover, r.quality_status,
        )
        for r in rows
    ]
    if not data:
        return 0
    with conn.cursor() as cur:
        cur.executemany(UPSERT_BAR_SQL, data)
    return len(data)


def load_bars_df(
    conn: DbConnection,
    codes: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust_type: str = "front",
) -> pd.DataFrame:
    clauses = ["adjust_type = %s"]
    params: List = [adjust_type]
    if codes:
        placeholders = ",".join(["%s"] * len(codes))
        clauses.append(f"code IN ({placeholders})")
        params.extend(codes)
    if start_date:
        clauses.append("date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("date <= %s")
        params.append(end_date)
    where = " AND ".join(clauses)
    sql = f"SELECT * FROM daily_bar WHERE {where} ORDER BY date, code"
    return pd.read_sql_query(sql, conn, params=params)


def list_bar_codes(conn: DbConnection, adjust_type: str = "front") -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT code FROM daily_bar WHERE adjust_type = %s ORDER BY code",
        (adjust_type,),
    ).fetchall()
    return [r[0] for r in rows]


def quality_stats(conn: DbConnection, adjust_type: str = "front") -> Dict[str, object]:
    rows = conn.execute(
        """
        SELECT quality_status, COUNT(*) AS cnt
        FROM daily_bar WHERE adjust_type = %s
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


def coverage_stats(conn: DbConnection, adjust_type: str = "front") -> Dict[str, object]:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT code) AS codes,
               COUNT(*) AS rows,
               MIN(date) AS min_date,
               MAX(date) AS max_date
        FROM daily_bar WHERE adjust_type = %s
        """,
        (adjust_type,),
    ).fetchone()
    if not row:
        return {}
    return {"codes": row[0], "rows": row[1], "min_date": row[2], "max_date": row[3]}


def market_latest_date(conn: DbConnection, adjust_type: str = "front") -> Optional[str]:
    row = conn.execute(
        "SELECT MAX(date) FROM daily_bar WHERE adjust_type = %s",
        (adjust_type,),
    ).fetchone()
    return row[0] if row and row[0] else None


def latest_bar_dates(conn: DbConnection, adjust_type: str = "front") -> Dict[str, str]:
    rows = conn.execute(
        """
        SELECT code, MAX(date) AS latest
        FROM daily_bar WHERE adjust_type = %s
        GROUP BY code
        """,
        (adjust_type,),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def bar_counts_by_code(
    conn: DbConnection,
    start: str,
    end: str,
    adjust_type: str = "front",
    codes: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    clauses = ["adjust_type = %s", "date >= %s", "date <= %s"]
    params: List = [adjust_type, start, end]
    if codes:
        placeholders = ",".join(["%s"] * len(codes))
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
    conn: DbConnection,
    code: str = "000001.SH",
    adjust_type: str = "front",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[str]:
    clauses = ["code = %s", "adjust_type = %s"]
    params: List = [code, adjust_type]
    if start:
        clauses.append("date >= %s")
        params.append(start)
    if end:
        clauses.append("date <= %s")
        params.append(end)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT date FROM daily_bar WHERE {where} ORDER BY date",
        params,
    ).fetchall()
    return [r[0] for r in rows]
