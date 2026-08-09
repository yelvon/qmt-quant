"""Financial statement sync."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Sequence

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import financial_rows_from_frame
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import upsert_financial
from qmt_quant.storage.sync_meta import get_meta, set_meta


def _financial_watermark(conn, sector: str) -> str | None:
    key = f"financial_watermark:{sector}"
    stored = get_meta(conn, key)
    if stored:
        return stored[:10]
    row = conn.execute(
        "SELECT MAX(announce_date) FROM financial_pershareindex WHERE announce_date IS NOT NULL"
    ).fetchone()
    return row[0][:10] if row and row[0] else None


def _codes_for_financial_sync(conn, codes: Sequence[str], watermark: str | None) -> List[str]:
    if not watermark:
        return list(codes)
    needing: List[str] = []
    for code in codes:
        row = conn.execute(
            """
            SELECT MAX(announce_date) FROM financial_pershareindex
            WHERE code = ? AND announce_date IS NOT NULL
            """,
            (code,),
        ).fetchone()
        latest = row[0][:10] if row and row[0] else None
        if not latest or latest < watermark:
            needing.append(code)
    return needing


def sync_financial(
    *,
    sector: str = "沪深A股",
    tables: Sequence[str] | None = None,
    incremental: bool = True,
) -> Dict[str, object]:
    run_migrations()
    table_list = list(tables or ["Balance", "Income", "CashFlow", "Pershareindex"])
    codes = resolve_universe(sector)
    client = XtDataClient()

    start_time = ""
    end_time = to_qmt_date(date.today().isoformat())
    sync_codes = list(codes)
    watermark: str | None = None

    with db_session() as conn:
        watermark = _financial_watermark(conn, sector)
        if incremental and watermark:
            buffer_start = (date.fromisoformat(watermark) - timedelta(days=90)).isoformat()
            start_time = to_qmt_date(buffer_start)
            sync_codes = _codes_for_financial_sync(conn, codes, watermark)

    if incremental and watermark and not sync_codes:
        return {
            "sector": sector,
            "tables": table_list,
            "codes": len(codes),
            "codes_synced": 0,
            "incremental": True,
            "skipped": True,
            "rows_written": 0,
            "watermark": watermark,
        }

    client.download_financial(sync_codes, table_list)
    data = client.get_financial_data(
        sync_codes,
        table_list,
        start_time=start_time,
        end_time=end_time,
    )

    written = 0
    max_announce: str | None = watermark if incremental else None
    with db_session() as conn:
        for code, tables_data in data.items():
            for table_name, df in tables_data.items():
                if table_name not in table_list:
                    continue
                for _, report_date, announce_date, payload in financial_rows_from_frame(
                    code, table_name, df
                ):
                    upsert_financial(conn, table_name, code, report_date, announce_date, payload)
                    written += 1
                    if announce_date:
                        ann = str(announce_date)[:10]
                        if not max_announce or ann > max_announce:
                            max_announce = ann
        if max_announce:
            set_meta(conn, f"financial_watermark:{sector}", max_announce)

    return {
        "sector": sector,
        "tables": table_list,
        "codes": len(codes),
        "codes_synced": len(sync_codes),
        "incremental": incremental,
        "start_time": start_time,
        "rows_written": written,
        "watermark": max_announce,
    }
