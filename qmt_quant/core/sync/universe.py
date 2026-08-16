"""Universe resolution."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Sequence

from qmt_quant.adapters.qmt.client import XtDataClient
from qmt_quant.config import get_settings
from qmt_quant.storage.database import db_session
from qmt_quant.storage.instruments import (
    NAME_MISSING_SQL as _NAME_MISSING_SQL,
    backfill_missing_names,
    backfill_names_after_sync,
)

__all__ = [
    "_NAME_MISSING_SQL",
    "backfill_instrument_names_after_sync",
    "backfill_missing_instrument_names",
    "list_days_since",
    "load_watchlist",
    "resolve_universe",
    "sync_universe",
]


def load_watchlist(path: Path | None = None) -> List[str]:
    from qmt_quant.core.watchlist import read_watchlist_codes

    return read_watchlist_codes(path)


def resolve_universe(sector: str | None = None) -> List[str]:
    settings = get_settings()
    sector_name = sector or settings.default_sector
    if sector_name in ("watchlist", "自选池", "我的自选池"):
        codes = load_watchlist()
        if codes:
            return codes
    try:
        client = XtDataClient()
        return client.get_sector_stocks(sector_name)
    except RuntimeError:
        return _universe_from_db()


def _universe_from_db() -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT code FROM daily_bar ORDER BY code"
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
        rows = conn.execute("SELECT code FROM instrument ORDER BY code").fetchall()
    return [r[0] for r in rows]


def backfill_instrument_names_after_sync(
    conn,
    codes: Sequence[str],
    *,
    client: XtDataClient | None = None,
    job_id: Optional[str] = None,
    batch_size: int = 50,
) -> int:
    """Fill instrument.name from QMT after bar sync (missing names only)."""
    return backfill_names_after_sync(
        conn,
        codes,
        client=client,
        job_id=job_id,
        batch_size=batch_size,
    )


def backfill_missing_instrument_names(
    conn,
    *,
    client: XtDataClient | None = None,
    limit: int = 300,
    sector: str | None = None,
) -> int:
    """Manual / API backfill for instruments missing names."""
    sector_codes = list(resolve_universe(sector)) if sector else None
    return backfill_missing_names(
        conn,
        client=client,
        limit=limit,
        sector_codes=sector_codes,
    )


def sync_universe(sector: str | None = None) -> int:
    codes = resolve_universe(sector)
    client = XtDataClient()
    with db_session() as conn:
        for code in codes:
            try:
                detail = client.get_instrument_detail(code)
            except Exception:
                detail = {}
            name = detail.get("InstrumentName") or detail.get("name") or code.split(".")[0]
            list_date = detail.get("OpenDate") or detail.get("list_date")
            delist_date = detail.get("ExpireDate") or detail.get("delist_date")
            is_st = _is_st(name, detail)
            conn.execute(
                """
                INSERT INTO instrument(code, name, list_date, delist_date, is_st, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT(code) DO UPDATE SET
                    name=EXCLUDED.name,
                    list_date=EXCLUDED.list_date,
                    delist_date=EXCLUDED.delist_date,
                    is_st=EXCLUDED.is_st,
                    updated_at=NOW()
                """,
                (
                    code,
                    name,
                    str(list_date) if list_date else None,
                    str(delist_date) if delist_date else None,
                    is_st,
                ),
            )
    return len(codes)


def _is_st(name: str, detail: dict) -> bool:
    if "ST" in (name or "").upper():
        return True
    flag = detail.get("IsST") or detail.get("is_st")
    return bool(flag)


def list_days_since(list_date: Optional[str], as_of: Optional[str] = None) -> Optional[int]:
    if not list_date:
        return None
    try:
        start = datetime.strptime(str(list_date)[:10], "%Y-%m-%d").date()
        end = datetime.strptime(as_of or date.today().isoformat(), "%Y-%m-%d").date()
        return (end - start).days
    except ValueError:
        return None
