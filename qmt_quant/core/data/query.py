"""SQL query layer for data browse."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from qmt_quant.adapters.qmt.client import normalize_code
from qmt_quant.core.ttl_cache import TtlCache
from qmt_quant.storage.database import DbConnection

_SORT_COL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_CODE_RE = re.compile(r"^\d{6}(\.(SH|SZ))?$", re.IGNORECASE)
_HAS_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_STOCK_NAME_ALIASES: Dict[str, str] = {
    "贵州茅台": "600519.SH",
    "茅台": "600519.SH",
    "平安银行": "000001.SZ",
    "招商银行": "600036.SH",
    "中国平安": "601318.SH",
    "五粮液": "000858.SZ",
    "宁德时代": "300750.SZ",
    "比亚迪": "002594.SZ",
}

_DAILY_BAR_SORT = {
    "code",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "change_pct",
    "name",
}

_INSTRUMENT_SORT = {"code", "name", "list_date", "delist_date", "is_st"}

_BAR_ROW_COLS = [
    "code",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "pre_close",
    "change_pct",
]

_DATE_RANGE_CACHE: TtlCache[Dict[str, Optional[str]]] = TtlCache(ttl_seconds=60.0)
_CROSS_SECTION_COUNT_CACHE: TtlCache[int] = TtlCache(ttl_seconds=30.0)

_CHANGE_PCT_EXPR = """
CASE WHEN pre_close > 0 THEN (close - pre_close) / pre_close * 100
     ELSE NULL END AS change_pct
"""

_EXCLUDE_ST_SQL = """
NOT EXISTS (
    SELECT 1 FROM instrument i_st
    WHERE i_st.code = daily_bar.code AND i_st.is_st = TRUE
)
"""


def list_available_adjust_types(conn: DbConnection) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT adjust_type FROM daily_bar ORDER BY adjust_type"
    ).fetchall()
    return [r[0] for r in rows]


def get_date_range(conn: DbConnection, adjust_type: str = "front") -> Dict[str, Optional[str]]:
    cache_key = adjust_type
    cached = _DATE_RANGE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    row = conn.execute(
        "SELECT MIN(date), MAX(date) FROM daily_bar WHERE adjust_type = %s",
        (adjust_type,),
    ).fetchone()
    result = {"min_date": row[0], "max_date": row[1]}
    _DATE_RANGE_CACHE.set(cache_key, result)
    return result


def clear_browse_query_cache() -> None:
    _DATE_RANGE_CACHE.clear()
    _CROSS_SECTION_COUNT_CACHE.clear()


def resolve_stock_code(conn: DbConnection, query: str) -> str:
    raw = (query or "").strip()
    if not raw:
        raise ValueError("missing_code")
    if _CODE_RE.match(raw):
        return normalize_code(raw)

    alias = _STOCK_NAME_ALIASES.get(raw)
    if not alias:
        alias = next((code for name, code in _STOCK_NAME_ALIASES.items() if name in raw or raw in name), None)
    if alias:
        return alias

    exact = conn.execute(
        """
        SELECT code FROM instrument
        WHERE code = %s OR name = %s
        ORDER BY code
        LIMIT 1
        """,
        (raw, raw),
    ).fetchone()
    if exact:
        return exact[0]

    like = f"%{raw}%"
    fuzzy = conn.execute(
        """
        SELECT code FROM instrument
        WHERE code LIKE %s OR name LIKE %s
        ORDER BY CASE WHEN name = %s THEN 0 WHEN name LIKE %s THEN 1 ELSE 2 END, code
        LIMIT 1
        """,
        (like, like, raw, f"{raw}%"),
    ).fetchone()
    if fuzzy:
        return fuzzy[0]

    if _HAS_CJK_RE.search(raw):
        raise ValueError("unknown_stock")

    if re.search(r"\d", raw):
        return normalize_code(raw)
    return normalize_code(raw)


def _validate_sort(sort_col: Optional[str], allowed: set[str]) -> str:
    col = sort_col or "code"
    if not _SORT_COL_RE.match(col) or col not in allowed:
        raise ValueError("invalid_sort_col")
    return col


def _fetch_instrument_names(conn: DbConnection, codes: List[str]) -> Dict[str, Optional[str]]:
    from qmt_quant.storage.instruments import get_name_map

    return get_name_map(conn, codes)


def _bar_rows_to_dicts(rows: List[tuple], names: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(zip(_BAR_ROW_COLS, row))
        item["name"] = names.get(item["code"])
        out.append(item)
    return out


def _cross_section_count_cache_key(
    date: str,
    adjust_type: str,
    code: Optional[str],
    exclude_st: bool,
) -> Tuple[str, str, bool, bool, str]:
    return (date, adjust_type, bool(code and code.strip()), exclude_st, (code or "").strip())


def _cross_section_count(
    conn: DbConnection,
    *,
    date: str,
    adjust_type: str,
    code: Optional[str],
    exclude_st: bool,
) -> int:
    cache_key = _cross_section_count_cache_key(date, adjust_type, code, exclude_st)
    cached = _CROSS_SECTION_COUNT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    code_filter = code.strip() if code else ""
    if code_filter:
        like = f"%{code_filter}%"
        st_clause = " AND (i.is_st IS NULL OR i.is_st = 0)" if exclude_st else ""
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM daily_bar b
            LEFT JOIN instrument i ON i.code = b.code
            WHERE b.date = %s AND b.adjust_type = %s
              AND (b.code LIKE %s OR i.name LIKE %s){st_clause}
            """,
            (date, adjust_type, like, like),
        ).fetchone()[0]
    elif exclude_st:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM daily_bar
            WHERE date = %s AND adjust_type = %s
              AND {_EXCLUDE_ST_SQL}
            """,
            (date, adjust_type),
        ).fetchone()[0]
    else:
        total = conn.execute(
            "SELECT COUNT(*) FROM daily_bar WHERE date = %s AND adjust_type = %s",
            (date, adjust_type),
        ).fetchone()[0]

    _CROSS_SECTION_COUNT_CACHE.set(cache_key, int(total))
    return int(total)


def _query_cross_section_bars_only(
    conn: DbConnection,
    *,
    date: str,
    adjust_type: str,
    sort: str,
    direction: str,
    page_size: int,
    offset: int,
    code: Optional[str],
    exclude_st: bool,
) -> List[tuple]:
    order_col = sort if sort != "change_pct" else "change_pct"
    order = f"{order_col} {direction}"
    params: List[Any] = [date, adjust_type]

    where = ["date = %s", "adjust_type = %s"]
    if exclude_st:
        where.append(_EXCLUDE_ST_SQL.strip())

    sql = f"""
        SELECT code, date, open, high, low, close, volume, amount, pre_close,
               {_CHANGE_PCT_EXPR}
        FROM daily_bar
        WHERE {" AND ".join(where)}
        ORDER BY {order}
        LIMIT %s OFFSET %s
    """
    params.extend([page_size, offset])
    return list(conn.execute(sql, params).fetchall())


def _query_cross_section_join(
    conn: DbConnection,
    *,
    date: str,
    adjust_type: str,
    sort: str,
    direction: str,
    page_size: int,
    offset: int,
    code: Optional[str],
    exclude_st: bool,
) -> Tuple[List[tuple], Dict[str, Optional[str]]]:
    order_col = {
        "code": "b.code",
        "date": "b.date",
        "open": "b.open",
        "high": "b.high",
        "low": "b.low",
        "close": "b.close",
        "volume": "b.volume",
        "amount": "b.amount",
        "name": "i.name",
        "change_pct": "change_pct",
    }.get(sort, "b.code")
    order = f"{order_col} {direction}"
    where = ["b.date = %s", "b.adjust_type = %s"]
    params: List[Any] = [date, adjust_type]
    if code:
        where.append("(b.code LIKE %s OR i.name LIKE %s)")
        like = f"%{code.strip()}%"
        params.extend([like, like])
    if exclude_st:
        where.append("(i.is_st IS NULL OR i.is_st = 0)")

    sql = f"""
        SELECT b.code, b.date, b.open, b.high, b.low, b.close,
               b.volume, b.amount, b.pre_close,
               CASE WHEN b.pre_close > 0 THEN (b.close - b.pre_close) / b.pre_close * 100
                    ELSE NULL END AS change_pct,
               i.name
        FROM daily_bar b
        LEFT JOIN instrument i ON i.code = b.code
        WHERE {" AND ".join(where)}
        ORDER BY {order}
        LIMIT %s OFFSET %s
    """
    rows = conn.execute(sql, [*params, page_size, offset]).fetchall()
    out: List[tuple] = []
    for row in rows:
        code_v, date_v, open_v, high_v, low_v, close_v, volume_v, amount_v, pre_close_v, change_pct_v, name_v = row
        out.append(
            (code_v, date_v, open_v, high_v, low_v, close_v, volume_v, amount_v, pre_close_v, change_pct_v)
        )
    return out, {row[0]: row[10] for row in rows}


def query_table(
    conn: DbConnection,
    table: str,
    view_mode: str,
    *,
    date: Optional[str] = None,
    code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    adjust_type: str = "front",
    q: Optional[str] = None,
    exclude_st: bool = False,
    page: int = 1,
    page_size: int = 100,
    sort_col: Optional[str] = None,
    sort_dir: str = "asc",
) -> Dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    offset = (page - 1) * page_size
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    if table == "daily_bar" and view_mode == "cross_section":
        if not date:
            raise ValueError("missing_date")
        sort = _validate_sort(sort_col, _DAILY_BAR_SORT)
        total = _cross_section_count(
            conn,
            date=date,
            adjust_type=adjust_type,
            code=code,
            exclude_st=exclude_st,
        )

        use_join = sort == "name" or (code and code.strip())
        if use_join:
            bar_rows, name_map = _query_cross_section_join(
                conn,
                date=date,
                adjust_type=adjust_type,
                sort=sort,
                direction=direction,
                page_size=page_size,
                offset=offset,
                code=code,
                exclude_st=exclude_st,
            )
            rows = _bar_rows_to_dicts(bar_rows, name_map)
        else:
            bar_rows = _query_cross_section_bars_only(
                conn,
                date=date,
                adjust_type=adjust_type,
                sort=sort,
                direction=direction,
                page_size=page_size,
                offset=offset,
                code=code,
                exclude_st=exclude_st,
            )
            names = _fetch_instrument_names(conn, [r[0] for r in bar_rows])
            rows = _bar_rows_to_dicts(bar_rows, names)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": rows,
        }

    if table == "daily_bar" and view_mode == "series":
        if not code:
            raise ValueError("missing_code")
        norm = resolve_stock_code(conn, code)
        sort = _validate_sort(sort_col or "date", _DAILY_BAR_SORT)
        order_col = {
            "code": "b.code",
            "date": "b.date",
            "open": "b.open",
            "high": "b.high",
            "low": "b.low",
            "close": "b.close",
            "volume": "b.volume",
            "amount": "b.amount",
            "change_pct": "change_pct",
            "name": "i.name",
        }.get(sort, "b.date")
        where = ["b.code = %s", "b.adjust_type = %s"]
        params = [norm, adjust_type]
        if date_from:
            where.append("b.date >= %s")
            params.append(date_from)
        if date_to:
            where.append("b.date <= %s")
            params.append(date_to)
        count_sql = f"SELECT COUNT(*) FROM daily_bar b WHERE {' AND '.join(where)}"
        total = conn.execute(count_sql, params).fetchone()[0]
        sql = f"""
            SELECT b.code, b.date, b.open, b.high, b.low, b.close,
                   b.volume, b.amount, b.pre_close,
                   CASE WHEN b.pre_close > 0 THEN (b.close - b.pre_close) / b.pre_close * 100
                        ELSE NULL END AS change_pct
            FROM daily_bar b
            WHERE {" AND ".join(where)}
            ORDER BY {order_col} {direction}
            LIMIT %s OFFSET %s
        """
        bar_rows = conn.execute(sql, [*params, page_size, offset]).fetchall()
        names = _fetch_instrument_names(conn, [norm])
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": _bar_rows_to_dicts(bar_rows, names),
        }

    if table == "instrument" and view_mode == "instrument_list":
        sort = _validate_sort(sort_col, _INSTRUMENT_SORT)
        where: List[str] = []
        params: List[Any] = []
        if q:
            where.append("(code LIKE %s OR name LIKE %s)")
            like = f"%{q}%"
            params.extend([like, like])
        if exclude_st:
            where.append("(is_st IS NULL OR is_st = 0)")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM instrument {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT code, name, list_date, delist_date, is_st
            FROM instrument {where_sql}
            ORDER BY {sort} {direction}
            LIMIT %s OFFSET %s
            """,
            [*params, page_size, offset],
        ).fetchall()
        cols = ["code", "name", "list_date", "delist_date", "is_st"]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [dict(zip(cols, r)) for r in rows],
        }

    raise ValueError(f"unsupported_view: {table}/{view_mode}")
