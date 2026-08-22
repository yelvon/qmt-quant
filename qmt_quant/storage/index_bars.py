"""Index bar / instrument repository (separate from stock daily_bar)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from qmt_quant.storage.database import DbConnection

UPSERT_INDEX_BAR_SQL = """
INSERT INTO index_daily_bar (
    code, date, open, high, low, close, volume, amount,
    pre_close, turnover, quality_status, source, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'qmt', NOW())
ON CONFLICT(code, date) DO UPDATE SET
    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
    volume=EXCLUDED.volume, amount=EXCLUDED.amount, pre_close=EXCLUDED.pre_close,
    turnover=EXCLUDED.turnover, quality_status=EXCLUDED.quality_status,
    updated_at=NOW()
"""

UPSERT_INDEX_INSTRUMENT_SQL = """
INSERT INTO index_instrument(code, name, kind, source_sector, updated_at)
VALUES (%s, %s, %s, %s, NOW())
ON CONFLICT(code) DO UPDATE SET
    name=COALESCE(EXCLUDED.name, index_instrument.name),
    kind=EXCLUDED.kind,
    source_sector=COALESCE(EXCLUDED.source_sector, index_instrument.source_sector),
    updated_at=NOW()
"""


@dataclass
class IndexBarRow:
    code: str
    date: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    pre_close: Optional[float] = None
    turnover: Optional[float] = None
    quality_status: str = "ok"


def upsert_index_instruments(
    conn: DbConnection,
    rows: Iterable[tuple[str, Optional[str], str, Optional[str]]],
) -> int:
    data = list(rows)
    if not data:
        return 0
    with conn.cursor() as cur:
        cur.executemany(UPSERT_INDEX_INSTRUMENT_SQL, data)
    return len(data)


def upsert_index_bars(conn: DbConnection, rows: Iterable[IndexBarRow]) -> int:
    data = [
        (
            r.code, r.date, r.open, r.high, r.low, r.close,
            r.volume, r.amount, r.pre_close, r.turnover, r.quality_status,
        )
        for r in rows
    ]
    if not data:
        return 0
    with conn.cursor() as cur:
        cur.executemany(UPSERT_INDEX_BAR_SQL, data)
    return len(data)


def index_codes_with_bars(conn: DbConnection, codes: Sequence[str]) -> set[str]:
    if not codes:
        return set()
    rows = conn.execute(
        "SELECT DISTINCT code FROM index_daily_bar WHERE code = ANY(%s)",
        (list(codes),),
    ).fetchall()
    return {r[0] for r in rows}


def list_index_instruments(conn: DbConnection) -> List[Dict[str, str]]:
    rows = conn.execute(
        """
        SELECT code, COALESCE(name, code), kind, COALESCE(source_sector, '')
        FROM index_instrument
        ORDER BY kind, code
        """
    ).fetchall()
    return [
        {"code": r[0], "name": r[1], "kind": r[2], "source_sector": r[3]}
        for r in rows
    ]


def get_index_name_map(conn: DbConnection, codes: Sequence[str]) -> Dict[str, Optional[str]]:
    if not codes:
        return {}
    rows = conn.execute(
        "SELECT code, name, kind FROM index_instrument WHERE code = ANY(%s)",
        (list(codes),),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_index_meta_map(conn: DbConnection, codes: Sequence[str]) -> Dict[str, Dict[str, Optional[str]]]:
    if not codes:
        return {}
    rows = conn.execute(
        "SELECT code, name, kind FROM index_instrument WHERE code = ANY(%s)",
        (list(codes),),
    ).fetchall()
    return {r[0]: {"name": r[1], "kind": r[2]} for r in rows}


def is_known_index(conn: DbConnection, code: str) -> bool:
    row = conn.execute("SELECT 1 FROM index_instrument WHERE code = %s", (code,)).fetchone()
    return row is not None


def index_date_range(conn: DbConnection) -> Dict[str, Optional[str]]:
    row = conn.execute("SELECT MIN(date), MAX(date) FROM index_daily_bar").fetchone()
    return {"min_date": row[0] if row else None, "max_date": row[1] if row else None}
