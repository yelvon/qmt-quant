"""Kline payload for charts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from qmt_quant.core.data.query import resolve_stock_code
from qmt_quant.storage.database import DbConnection

MAX_KLINE_BARS = 8000


def build_kline_payload(
    conn: DbConnection,
    code: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    adjust: str = "front",
) -> Dict[str, Any]:
    if not code or not str(code).strip():
        raise ValueError("missing_code")
    norm = resolve_stock_code(conn, code)
    clauses = ["code = %s", "adjust_type = %s"]
    params: List[Any] = [norm, adjust]
    if date_from:
        clauses.append("date >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("date <= %s")
        params.append(date_to)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT date, open, high, low, close, volume
        FROM daily_bar WHERE {where}
        ORDER BY date ASC
        LIMIT %s
        """,
        [*params, MAX_KLINE_BARS + 1],
    ).fetchall()
    truncated = len(rows) > MAX_KLINE_BARS
    if truncated:
        rows = rows[:MAX_KLINE_BARS]
    if not rows:
        return {
            "ok": True,
            "code": norm,
            "adjust": adjust,
            "empty": True,
            "hint": "无数据，请先在「② 准备数据」同步日线，或调整日期/复权/股票",
            "dates": [],
            "ohlc": [],
            "volume": [],
        }
    dates = [r[0] for r in rows]
    ohlc = [[r[1], r[4], r[3], r[2]] for r in rows]
    volume = [r[5] for r in rows]
    payload: Dict[str, Any] = {
        "ok": True,
        "code": norm,
        "adjust": adjust,
        "empty": False,
        "dates": dates,
        "ohlc": ohlc,
        "volume": volume,
    }
    if truncated:
        payload["truncated"] = True
        payload["hint"] = f"仅展示最近 {MAX_KLINE_BARS} 根 K 线，请缩小日期范围查看更早数据"
    return payload
