"""Universe resolution."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional

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


def refresh_instrument_names(
    conn,
    *,
    q: str | None = None,
    codes: List[str] | None = None,
    limit: int = 40,
    client: XtDataClient | None = None,
) -> int:
    """Fill missing instrument.name rows (lazy, for browse/search)."""
    if client is None:
        client = XtDataClient()
    params: List[Any] = []
    if codes:
        placeholders = ",".join(["%s"] * len(codes))
        sql = f"""
            SELECT code FROM instrument
            WHERE code IN ({placeholders}) AND (name IS NULL OR name = '' OR name = code)
        """
        params = list(codes)
    elif q:
        q = q.strip()
        if re.search(r"[\u4e00-\u9fff]", q):
            from qmt_quant.core.data.query import _STOCK_NAME_ALIASES

            alias = _STOCK_NAME_ALIASES.get(q) or next(
                (code for name, code in _STOCK_NAME_ALIASES.items() if name in q or q in name),
                None,
            )
            if alias:
                sql = "SELECT code FROM instrument WHERE code = %s"
                params = [alias]
            else:
                sql = """
                    SELECT i.code FROM instrument i
                    WHERE (i.name IS NULL OR i.name = '' OR i.name = i.code)
                      AND EXISTS (SELECT 1 FROM daily_bar b WHERE b.code = i.code)
                    ORDER BY i.code
                    LIMIT %s
                """
                params = [limit * 5]
        else:
            like = f"%{q}%"
            sql = """
                SELECT i.code FROM instrument i
                WHERE (i.name IS NULL OR i.name = '' OR i.name = i.code)
                  AND (i.code LIKE %s OR i.code IN (
                        SELECT DISTINCT code FROM daily_bar WHERE code LIKE %s
                  ))
                ORDER BY i.code
                LIMIT %s
            """
            params = [like, like, limit]
    else:
        sql = """
            SELECT i.code FROM instrument i
            WHERE (i.name IS NULL OR i.name = '' OR i.name = i.code)
              AND EXISTS (SELECT 1 FROM daily_bar b WHERE b.code = i.code)
            ORDER BY i.code
            LIMIT %s
        """
        params = [limit]

    rows = conn.execute(sql, params).fetchall()
    updated = 0
    for (code,) in rows:
        try:
            detail = client.get_instrument_detail(code)
        except Exception:
            continue
        name = detail.get("InstrumentName") or detail.get("name")
        if not name or name == code.split(".")[0]:
            continue
        conn.execute(
            "UPDATE instrument SET name = %s, updated_at = NOW() WHERE code = %s",
            (name, code),
        )
        updated += 1
        if q and q.strip() in (name or ""):
            break
    return updated


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
