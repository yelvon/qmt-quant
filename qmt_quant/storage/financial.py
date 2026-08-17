"""Financial data repository."""

from __future__ import annotations

import json
from typing import Dict, Optional, Sequence

from qmt_quant.storage.database import DbConnection

TABLE_MAP = {
    "Balance": "financial_balance",
    "Income": "financial_income",
    "CashFlow": "financial_cashflow",
    "Pershareindex": "financial_pershareindex",
}


def upsert_financial(
    conn: DbConnection,
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
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT(code, report_date) DO UPDATE SET
            announce_date=EXCLUDED.announce_date,
            data_json=EXCLUDED.data_json,
            updated_at=NOW()
        """,
        (code, report_date, announce_date, json.dumps(payload, ensure_ascii=False)),
    )


def load_financial_asof(
    conn: DbConnection,
    table_key: str,
    code: str,
    as_of_date: str,
) -> Optional[Dict]:
    table = TABLE_MAP[table_key]
    row = conn.execute(
        f"""
        SELECT data_json FROM {table}
        WHERE code = %s AND announce_date IS NOT NULL AND announce_date <= %s
        ORDER BY announce_date DESC LIMIT 1
        """,
        (code, as_of_date),
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def load_financial_batch_asof(
    conn: DbConnection,
    table_key: str,
    codes: Sequence[str],
    as_of_date: str,
) -> Dict[str, Dict]:
    """Load each instrument's latest announced record in one PostgreSQL query."""
    if not codes:
        return {}
    table = TABLE_MAP[table_key]
    rows = conn.execute(
        f"""
        SELECT DISTINCT ON (code) code, data_json
        FROM {table}
        WHERE code = ANY(%s) AND announce_date IS NOT NULL AND announce_date <= %s
        ORDER BY code, announce_date DESC, report_date DESC
        """,
        (list(dict.fromkeys(codes)), as_of_date),
    ).fetchall()
    return {str(code): json.loads(payload) for code, payload in rows}


def load_financial_panel_asof(
    conn: DbConnection,
    table_key: str,
    codes: Sequence[str],
    as_of_dates: Sequence[str],
) -> Dict[str, Dict[str, Dict]]:
    """Load point-in-time records for many dates/codes without per-stock queries."""
    if not codes or not as_of_dates:
        return {}
    table = TABLE_MAP[table_key]
    rows = conn.execute(
        f"""
        SELECT d.as_of_date, f.code, f.data_json
        FROM unnest(%s::date[]) AS d(as_of_date)
        CROSS JOIN unnest(%s::text[]) AS c(code)
        JOIN LATERAL (
            SELECT code, data_json
            FROM {table}
            WHERE code = c.code
              AND announce_date IS NOT NULL
              AND announce_date <= d.as_of_date
            ORDER BY announce_date DESC, report_date DESC
            LIMIT 1
        ) AS f ON TRUE
        """,
        (list(dict.fromkeys(as_of_dates)), list(dict.fromkeys(codes))),
    ).fetchall()
    panel: Dict[str, Dict[str, Dict]] = {}
    for as_of_date, code, payload in rows:
        panel.setdefault(str(as_of_date), {})[str(code)] = json.loads(payload)
    return panel
