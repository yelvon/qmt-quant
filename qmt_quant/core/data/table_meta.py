"""Table metadata for data browse."""

from __future__ import annotations

from typing import Any, Dict, List

ADJUST_OPTIONS = [
    {"id": "front", "label": "前复权"},
    {"id": "none", "label": "不复权"},
    {"id": "back", "label": "后复权"},
]

_TABLES: Dict[str, Dict[str, Any]] = {
    "daily_bar": {
        "table": "daily_bar",
        "label": "日线行情",
        "view_modes": ["cross_section", "series"],
        "columns": [
            {"id": "code", "label": "代码"},
            {"id": "name", "label": "名称"},
            {"id": "date", "label": "日期"},
            {"id": "open", "label": "开盘"},
            {"id": "high", "label": "最高"},
            {"id": "low", "label": "最低"},
            {"id": "close", "label": "收盘"},
            {"id": "volume", "label": "成交量"},
            {"id": "amount", "label": "成交额"},
            {"id": "change_pct", "label": "涨跌幅%"},
        ],
        "adjust_options": ADJUST_OPTIONS,
    },
    "instrument": {
        "table": "instrument",
        "label": "股票列表",
        "view_modes": ["instrument_list"],
        "columns": [
            {"id": "code", "label": "代码"},
            {"id": "name", "label": "名称"},
            {"id": "list_date", "label": "上市日"},
            {"id": "delist_date", "label": "退市日"},
            {"id": "is_st", "label": "ST"},
        ],
        "adjust_options": [],
    },
}


def list_tables() -> List[Dict[str, Any]]:
    return [
        {"id": k, "label": v["label"], "view_modes": v["view_modes"]}
        for k, v in _TABLES.items()
    ]


def get_table_meta(table: str) -> Dict[str, Any]:
    if table not in _TABLES:
        raise ValueError(f"unknown_table: {table}")
    return dict(_TABLES[table])
