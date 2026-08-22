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

    if job_id and not on_batch_done:
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
    on_batch_done: Optional[Callable[[int, int], None]] = None,
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
            on_batch_done=on_batch_done,
        )

    with db_session() as conn:
        market_latest = market_latest_date(conn, adjust_type)
        if market_latest:
            set_meta(conn, f"bars_market_latest:{adjust_type}", market_latest)

    try:
        sync_calendar_from_qmt(start_date=ranges[0].get("start"), end_date=ranges[0].get("end"))
    except Exception:
        sync_calendar_from_bars()

    names_backfilled = 0
    try:
        with db_session() as conn:
            from qmt_quant.storage.instruments import backfill_names_after_sync

            names_backfilled = backfill_names_after_sync(
                conn,
                codes,
                client=client,
                job_id=job_id,
            )
    except Exception:
        pass

    result: Dict[str, object] = {
        "sector": sector_name,
        "codes": len(codes),
        "date_ranges": ranges,
        "bars_written": written,
        "adjust_type": adjust_type,
    }
    if names_backfilled:
        result["names_backfilled"] = names_backfilled

    if settings.auto_export_catalog:
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(adjust_type=adjust_type, codes=codes)
    if written:
        from qmt_quant.core.catalog.export import clear_price_matrix_cache
        from qmt_quant.core.data.query import clear_browse_query_cache
        from qmt_quant.core.sync.check import clear_data_check_cache

        clear_price_matrix_cache()
        clear_browse_query_cache()
        clear_data_check_cache()

    lookback_starts = [str(dr.get("start") or "") for dr in ranges if dr.get("start")]
    lookback_ends = [str(dr.get("end") or "") for dr in ranges if dr.get("end")]
    try:
        from qmt_quant.core.sync.index_sync import sync_index_bars

        result.update(
            sync_index_bars(
                client=client,
                job_start=lookback_starts[0] if lookback_starts else "",
                job_end=lookback_ends[-1] if lookback_ends else "",
                job_id=job_id,
                repair=True,
                lookback_start=min(lookback_starts) if lookback_starts else None,
                lookback_end=max(lookback_ends) if lookback_ends else None,
            )
        )
    except Exception as exc:
        result["index_codes"] = 0
        result["index_bars_written"] = 0
        result["index_failed"] = ["*"]
        result["index_error"] = str(exc)
        result["industry_source_sector"] = None
    return result


def run_check_and_repair(
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    detailed: bool = True,
    codes: Optional[Sequence[str]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    if job_id:
        report_job_progress(
            job_id,
            0.05,
            "分析数据缺口…",
            step="check",
            step_label="检测缺口",
        )

    check = analyze_gaps(
        sector=sector,
        adjust_type=adjust_type,
        detailed=detailed,
        include_repair_plan=True,
    )
    if not check.get("needs_repair") and not codes:
        if job_id:
            report_job_progress(job_id, 1.0, "数据正常，无需修复", step="check", step_label="检测缺口")
        return {"check": check, "repair": {"skipped": True, "reason": "no repair needed"}}

    if codes:
        plan = build_repair_plan(sector=sector, adjust_type=adjust_type, codes=list(codes))
    else:
        plan = RepairPlan.from_dict(check.get("repair_plan") or {})

    code_count = len(plan.codes or [])
    if job_id:
        report_job_progress(
            job_id,
            0.12,
            f"准备修复 {code_count} 只股票…" if code_count else "准备修复…",
            step="repair",
            step_label="补数修复",
        )

    def _repair_progress(processed: int, total: int) -> None:
        if not job_id or total <= 0:
            return
        progress = 0.12 + 0.76 * (processed / total)
        report_job_progress(
            job_id,
            progress,
            sync_progress_message(
                processed,
                total,
                job_id=job_id,
                prefix="修复中",
                progress=progress,
            ),
            step="repair",
            step_label="补数修复",
            detail=f"{processed}/{total} 只",
        )

    repair = sync_bars_repair(
        plan,
        sector=sector,
        job_id=job_id,
        on_batch_done=_repair_progress if job_id else None,
    )
    from qmt_quant.core.sync.check import clear_data_check_cache

    clear_data_check_cache()

    if job_id:
        report_job_progress(job_id, 0.90, "复检数据状态…", step="verify", step_label="复检")

    post_check = analyze_gaps(
        sector=sector,
        adjust_type=adjust_type,
        detailed=detailed,
        include_repair_plan=False,
    )

    if job_id:
        report_job_progress(job_id, 0.98, "修复完成", step="save", step_label="完成")

    return {"check": check, "repair": repair, "post_check": post_check}
