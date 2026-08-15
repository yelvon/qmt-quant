"""Financial statement sync."""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Set, Tuple

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import financial_rows_from_frame
from qmt_quant.config import get_settings
from qmt_quant.core.jobs.context import (
    JobCancelled,
    is_job_cancelled,
    report_job_progress,
    sync_progress_message,
)
from qmt_quant.core.sync.parallel import iter_chunks, qmt_semaphore, run_batches_parallel
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import connect, db_session, run_migrations
from qmt_quant.storage.financial import upsert_financial
from qmt_quant.storage.sync_meta import get_meta, set_meta

_WRITE_BATCH_SIZE = 200
_PROGRESS_START = 0.08
_PROGRESS_END = 0.95


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


def _sync_progress(processed: int, total: int) -> float:
    if total <= 0:
        return _PROGRESS_START
    span = _PROGRESS_END - _PROGRESS_START
    return _PROGRESS_START + span * (processed / total)


def _build_checkpoint(
    *,
    remaining_codes: Sequence[str],
    processed: int,
    total: int,
    sector: str,
    tables: Sequence[str],
    incremental: bool,
    start_time: str,
    end_time: str,
    watermark: str | None,
) -> Dict[str, object]:
    return {
        "remaining_codes": list(remaining_codes),
        "processed": processed,
        "total": total,
        "sector": sector,
        "tables": list(tables),
        "incremental": incremental,
        "start_time": start_time,
        "end_time": end_time,
        "watermark": watermark,
    }


def _raise_if_cancelled(
    *,
    job_id: Optional[str],
    code_list: Sequence[str],
    index: int,
    processed_base: int,
    total: int,
    sector: str,
    tables: Sequence[str],
    incremental: bool,
    start_time: str,
    end_time: str,
    watermark: str | None,
    written: int,
    remaining_codes: Optional[Sequence[str]] = None,
) -> None:
    if not job_id or not is_job_cancelled(job_id):
        return
    remaining = list(remaining_codes if remaining_codes is not None else code_list[index:])
    processed = processed_base + (total - len(remaining))
    progress = _sync_progress(processed, total)
    raise JobCancelled(
        _build_checkpoint(
            remaining_codes=remaining,
            processed=processed,
            total=total,
            sector=sector,
            tables=tables,
            incremental=incremental,
            start_time=start_time,
            end_time=end_time,
            watermark=watermark,
        ),
        progress=progress,
        partial_result={"rows_written": written, "processed": processed},
        message=sync_progress_message(processed, total, job_id=job_id, prefix="财报同步已中断"),
    )


def _write_tables_for_code(
    conn,
    code: str,
    tables_data: Dict[str, object],
    table_list: Sequence[str],
    max_announce: str | None,
) -> Tuple[int, str | None]:
    written = 0
    pending = 0
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
    return written, max_announce


def sync_financial(
    *,
    sector: str = "沪深A股",
    tables: Sequence[str] | None = None,
    incremental: bool = True,
    job_id: Optional[str] = None,
    resume_checkpoint: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    batch_size = settings.sync_batch_size
    table_list = list(tables or ["Balance", "Income", "CashFlow", "Pershareindex"])
    client = XtDataClient()

    processed_base = 0
    total_codes = 0
    watermark: str | None = None
    start_time = ""
    end_time = to_qmt_date(date.today().isoformat())

    if resume_checkpoint:
        sync_codes = list(resume_checkpoint.get("remaining_codes") or [])
        sector = str(resume_checkpoint.get("sector") or sector)
        table_list = list(resume_checkpoint.get("tables") or table_list)
        incremental = bool(resume_checkpoint.get("incremental", incremental))
        start_time = str(resume_checkpoint.get("start_time") or "")
        end_time = str(resume_checkpoint.get("end_time") or end_time)
        watermark = resume_checkpoint.get("watermark")  # type: ignore[assignment]
        processed_base = int(resume_checkpoint.get("processed") or 0)
        total_codes = int(resume_checkpoint.get("total") or (processed_base + len(sync_codes)))
        if job_id:
            report_job_progress(
                job_id,
                _sync_progress(processed_base, total_codes),
                f"续传财报同步（已完成 {processed_base}/{total_codes}）",
            )
    else:
        codes = resolve_universe(sector)
        sync_codes = list(codes)

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

        total_codes = len(sync_codes)
        if job_id:
            report_job_progress(
                job_id,
                _PROGRESS_START,
                sync_progress_message(
                    0,
                    total_codes,
                    job_id=job_id,
                    prefix=f"正在从 QMT 下载财报",
                    progress=_PROGRESS_START,
                ),
            )

    if not sync_codes:
        return {
            "sector": sector,
            "tables": table_list,
            "codes": total_codes,
            "codes_synced": 0,
            "incremental": incremental,
            "skipped": True,
            "rows_written": 0,
            "watermark": watermark,
        }

    if total_codes <= 0:
        total_codes = processed_base + len(sync_codes)

    written = 0
    max_announce: str | None = watermark if incremental else None
    code_list = list(sync_codes)
    chunks = iter_chunks(code_list, batch_size)
    completed_codes: Set[str] = set()
    state_lock = threading.Lock()

    def _cancel_check() -> None:
        with state_lock:
            remaining = [c for c in code_list if c not in completed_codes]
            done = len(completed_codes)
        _raise_if_cancelled(
            job_id=job_id,
            code_list=code_list,
            index=done,
            processed_base=processed_base,
            total=total_codes,
            sector=sector,
            tables=table_list,
            incremental=incremental,
            start_time=start_time,
            end_time=end_time,
            watermark=watermark,
            written=written,
            remaining_codes=remaining,
        )

    def _process_chunk(chunk: Sequence[str]) -> int:
        nonlocal written, max_announce
        with qmt_semaphore():
            data = client.fetch_financial_data(
                chunk,
                table_list,
                start_time=start_time,
                end_time=end_time,
            )
        local_written = 0
        local_max = max_announce
        conn = connect()
        try:
            for code, tables_data in data.items():
                chunk_written, local_max = _write_tables_for_code(
                    conn, code, tables_data, table_list, local_max
                )
                local_written += chunk_written
            conn.commit()
        finally:
            conn.close()
        with state_lock:
            completed_codes.update(chunk)
            written += local_written
            if local_max and (not max_announce or local_max > max_announce):
                max_announce = local_max
            done = processed_base + len(completed_codes)
        if job_id:
            progress = _sync_progress(done, total_codes)
            report_job_progress(
                job_id,
                progress,
                sync_progress_message(
                    done,
                    total_codes,
                    job_id=job_id,
                    prefix="财报同步",
                    progress=progress,
                ),
            )
        return local_written

    run_batches_parallel(
        chunks,
        concurrency=settings.sync_concurrency,
        job_id=job_id,
        cancel_check=_cancel_check,
        worker=_process_chunk,
    )

    conn = connect()
    try:
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
        "codes": total_codes,
        "codes_synced": len(code_list),
        "incremental": incremental,
        "start_time": start_time,
        "rows_written": written,
        "watermark": max_announce,
    }
