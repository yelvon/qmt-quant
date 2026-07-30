"""Financial data repository."""

from __future__ import annotations

import json
import sqlite3
from typing import Dict, Iterable, List, Optional

TABLE_MAP = {
    "Balance": "financial_balance",
    "Income": "financial_income",
    "CashFlow": "financial_cashflow",
    "Pershareindex": "financial_pershareindex",
}


def upsert_financial(
    conn: sqlite3.Connection,
    table_key: str,
    code: str,
    report_date: str,
    announce_date: Optional[str],
    payload: Dict,
) -> None:
    table = TABLE_MAP[table_key]
    conn.execute(
        f"""
        INSERT INTO {table}(code, report_date, announce_date, data_json, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(code, report_date) DO UPDATE SET
            announce_date=excluded.announce_date,
            data_json=excluded.data_json,
            updated_at=datetime('now')
        """,
        (code, report_date, announce_date, json.dumps(payload, ensure_ascii=False)),
    )


def load_financial_asof(
    conn: sqlite3.Connection,
    table_key: str,
    code: str,
    as_of_date: str,
) -> Optional[Dict]:
    table = TABLE_MAP[table_key]
    row = conn.execute(
        f"""
        SELECT data_json FROM {table}
        WHERE code = ? AND announce_date IS NOT NULL AND announce_date <= ?
        ORDER BY announce_date DESC LIMIT 1
        """,
        (code, as_of_date),
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])
