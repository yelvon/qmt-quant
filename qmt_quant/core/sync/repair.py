"""Targeted bar gap repair."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import bars_from_dataframe
from qmt_quant.config import get_settings
from qmt_quant.core.jobs.context import JobCancelled, is_job_cancelled, report_job_progress, sync_progress_message
from qmt_quant.core.sync.gaps import RepairPlan, analyze_gaps, build_repair_plan
from qmt_quant.core.sync.calendar import sync_calendar_from_bars, sync_calendar_from_qmt
from qmt_quant.core.sync.parallel import iter_chunks, qmt_semaphore, run_batches_parallel
from qmt_quant.storage.bars import market_latest_date, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import set_meta


def _sync_progress(progress: float, processed: int, total: int) -> float:
    if total <= 0:
        return progress
    return 0.05 + 0.90 * (processed / total)


def _build_checkpoint(
    *,
    remaining_codes: Sequence[str],
    processed: int,
    total: int,
    start: str,
    end: str,
    sector: str,
    adjust_type: str,
    mode: str,
) -> Dict[str, Any]:
    return {
        "remaining_codes": list(remaining_codes),
        "processed": processed,
        "total": total,
        "start": start,
        "end": end,
        "sector": sector,
        "adjust_type": adjust_type,
        "mode": mode,
    }


def _raise_if_cancelled(
    *,
    job_id: Optional[str],
    code_list: Sequence[str],
    index: int,
    processed_base: int,
    total: int,
    start: str,
    end: str,
    sector: str,
    adjust_type: str,
    mode: str,
    written: int,
    prefix: str = "已中断",
    remaining_codes: Optional[Sequence[str]] = None,
) -> None:
    if not job_id or not is_job_cancelled(job_id):
        return
    processed = processed_base + index
    progress = _sync_progress(0.05, processed, total)
    remaining = list(remaining_codes if remaining_codes is not None else code_list[index:])
    raise JobCancelled(
        _build_checkpoint(
            remaining_codes=remaining,
            processed=processed_base + (total - len(remaining)),
            total=total,
            start=start,
            end=end,
            sector=sector,
            adjust_type=adjust_type,
            mode=mode,
        ),
        progress=progress,
        partial_result={"bars_written": written, "processed": processed_base + (total - len(remaining))},
        message=sync_progress_message(
            processed_base + (total - len(remaining)), total, job_id=job_id, prefix=prefix
        ),
    )


def _fetch_and_upsert(
    client: XtDataClient,
    codes: Sequence[str],
    start: str,
    end: str,
    adjust_type: str,
    dividend: str,
    batch_size: int,
    *,
    job_id: Optional[str] = None,
    processed_base: int = 0,
    total_codes: Optional[int] = None,
    sector: str = "",
    mode: str = "incremental",
    on_batch_done: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Download bars from QMT and upsert in short DB transactions (no long-held locks)."""
    settings = get_settings()
    written = 0
    code_list = list(codes)
    total = total_codes if total_codes is not None else len(code_list)
    qmt_start = to_qmt_date(start)
    qmt_end = to_qmt_date(end)
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
            total=total,
            start=start,
            end=end,
            sector=sector,
            adjust_type=adjust_type,
            mode=mode,
            written=written,
            remaining_codes=remaining,
        )

    def _process_chunk(chunk: Sequence[str]) -> int:
        nonlocal written
        with qmt_semaphore():
            data = client.fetch_market_bars(
                chunk,
                period="1d",
                start_time=qmt_start,
                end_time=qmt_end,
                dividend_type=dividend,
            )
        local_written = 0
        with db_session() as conn:
            for code, df in data.items():
                rows = bars_from_dataframe(code, df, adjust_type=adjust_type)
                local_written += upsert_bars(conn, rows)
        with state_lock:
            completed_codes.update(chunk)
            written += local_written
            done = processed_base + len(completed_codes)
        if on_batch_done:
            on_batch_done(done, total)
        elif job_id:
            progress = _sync_progress(0.05, done, total)
            report_job_progress(
                job_id,
                progress,
                sync_progress_message(done, total, job_id=job_id, progress=progress),
            )
        return local_written

    if job_id:
        report_job_progress(
            job_id,
            _sync_progress(0.05, processed_base, total),
            sync_progress_message(
                processed_base,
                total,
                job_id=job_id,
                prefix="正在下载",
                progress=_sync_progress(0.05, processed_base, total),
            ),
        )

    run_batches_parallel(
        chunks,
        concurrency=settings.sync_concurrency,
        job_id=job_id,
        cancel_check=_cancel_check,
        worker=_process_chunk,
    )
    return written


def sync_bars_repair(
    plan: RepairPlan,
    *,
    sector: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    from qmt_quant.core.presets import DIVIDEND_MAP

    adjust_type = plan.adjust_type or settings.bar_adjust_type
    dividend = DIVIDEND_MAP.get(adjust_type, "front")
    client = XtDataClient()
    codes = plan.codes
    if not codes:
        return {"codes": 0, "bars_written": 0, "skipped": True}

    written = 0
    ranges = plan.date_ranges or [{"start": "", "end": ""}]
    sector_name = sector or plan.sector or settings.default_sector
    for dr in ranges:
        start, end = dr.get("start", ""), dr.get("end", "")
        if not start or not end:
            continue
        written += _fetch_and_upsert(
            client,
            codes,
            start,
            end,
            adjust_type,
            dividend,
            settings.sync_batch_size,
            job_id=job_id,
            sector=sector_name,
            mode="repair",
        )

    with db_session() as conn:
        market_latest = market_latest_date(conn, adjust_type)
        if market_latest:
            set_meta(conn, f"bars_market_latest:{adjust_type}", market_latest)

    try:
        sync_calendar_from_qmt(start_date=ranges[0].get("start"), end_date=ranges[0].get("end"))
    except Exception:
        sync_calendar_from_bars()

    result: Dict[str, object] = {
        "sector": sector_name,
        "codes": len(codes),
        "date_ranges": ranges,
        "bars_written": written,
        "adjust_type": adjust_type,
    }

    if settings.auto_export_catalog:
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(adjust_type=adjust_type, codes=codes)
    return result


def run_check_and_repair(
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    detailed: bool = True,
    codes: Optional[Sequence[str]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    check = analyze_gaps(
        sector=sector,
        adjust_type=adjust_type,
        detailed=detailed,
        include_repair_plan=True,
    )
    if not check.get("needs_repair") and not codes:
        return {"check": check, "repair": {"skipped": True, "reason": "no repair needed"}}

    if codes:
        plan = build_repair_plan(sector=sector, adjust_type=adjust_type, codes=list(codes))
    else:
        plan = RepairPlan.from_dict(check.get("repair_plan") or {})
    repair = sync_bars_repair(plan, sector=sector, job_id=job_id)
    from qmt_quant.core.sync.check import clear_data_check_cache

    clear_data_check_cache()
    post_check = analyze_gaps(
        sector=sector,
        adjust_type=adjust_type,
        detailed=detailed,
        include_repair_plan=False,
    )
    return {"check": check, "repair": repair, "post_check": post_check}
