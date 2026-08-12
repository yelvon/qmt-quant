"""Universe resolution."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from qmt_quant.adapters.qmt.client import XtDataClient, normalize_code
from qmt_quant.config import get_settings
from qmt_quant.storage.database import db_session


def load_watchlist(path: Path | None = None) -> List[str]:
    settings = get_settings()
    p = path or settings.resolve_path(settings.watchlist_path)
    if not p.exists():
        return []
    codes = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            codes.append(normalize_code(line))
    return codes


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
