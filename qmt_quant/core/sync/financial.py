"""Financial statement sync."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import financial_rows_from_frame
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import connect, db_session, run_migrations
from qmt_quant.storage.financial import upsert_financial
from qmt_quant.storage.sync_meta import get_meta, set_meta

_WRITE_BATCH_SIZE = 200


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
    rows = conn.execute(
        """
        SELECT code, MAX(announce_date) AS latest
        FROM financial_pershareindex
        WHERE announce_date IS NOT NULL
        GROUP BY code
        """
    ).fetchall()
    latest_by_code = {row[0]: str(row[1])[:10] for row in rows if row[1]}
    needing: List[str] = []
    for code in codes:
        latest = latest_by_code.get(code)
        if not latest or latest < watermark:
            needing.append(code)
    return needing


def sync_financial(
    *,
    sector: str = "沪深A股",
    tables: Sequence[str] | None = None,
    incremental: bool = True,
    job_id: Optional[str] = None,
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

    if job_id:
        report_job_progress(
            job_id,
            0.08,
            f"正在从 QMT 下载财报（{len(sync_codes)} 只股票）…",
        )

    client.download_financial(sync_codes, table_list)
    data = client.get_financial_data(
        sync_codes,
        table_list,
        start_time=start_time,
        end_time=end_time,
    )

    written = 0
    pending = 0
    max_announce: str | None = watermark if incremental else None
    total_codes = max(len(data), 1)
    processed_codes = 0

    conn = connect()
    try:
        for code, tables_data in data.items():
            for table_name, df in tables_data.items():
                if table_name not in table_list:
                    continue
                for _, report_date, announce_date, payload in financial_rows_from_frame(
                    code, table_name, df
                ):
                    upsert_financial(conn, table_name, code, report_date, announce_date, payload)
                    written += 1
                    pending += 1
                    if announce_date:
                        ann = str(announce_date)[:10]
                        if not max_announce or ann > max_announce:
                            max_announce = ann
                    if pending >= _WRITE_BATCH_SIZE:
                        conn.commit()
                        pending = 0
            processed_codes += 1
            if job_id and processed_codes % 25 == 0:
                report_job_progress(
                    job_id,
                    0.1 + 0.85 * (processed_codes / total_codes),
                    f"已写入财报 {processed_codes}/{total_codes} 只股票",
                )
        conn.commit()
        if max_announce:
            set_meta(conn, f"financial_watermark:{sector}", max_announce)
        conn.commit()
    finally:
        conn.close()

    if job_id:
        report_job_progress(job_id, 0.98, f"财报写入完成，共 {written} 条")

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
