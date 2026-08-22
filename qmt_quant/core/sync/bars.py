"""Daily bar sync."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Literal, Optional

from qmt_quant.adapters.qmt.client import XtDataClient
from qmt_quant.config import get_settings
from qmt_quant.core.jobs.context import JobCancelled, is_job_cancelled, report_job_progress, sync_progress_message
from qmt_quant.core.presets import DIVIDEND_MAP, resolve_range_preset
from qmt_quant.core.sync.calendar import sync_calendar_from_bars, sync_calendar_from_qmt
from qmt_quant.core.sync.gaps import RepairPlan
from qmt_quant.core.sync.repair import _fetch_and_upsert, sync_bars_repair
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.core.sync.universe_stats import (
    ensure_instrument_codes,
    record_universe_count,
)
from qmt_quant.storage.bars import market_latest_date
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import set_meta


SyncMode = Literal["incremental", "full", "repair"]


def _maybe_auto_repair(
    *,
    sector: str,
    adjust_type: str,
    incremental_days: int,
    job_id: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    settings = get_settings()
    if not settings.sync_auto_repair:
        return None
    from qmt_quant.core.sync.check import run_data_check

    check = run_data_check(sector=sector, adjust_type=adjust_type, detailed=False)
    if not check.get("needs_repair"):
        return None
    plan = RepairPlan.from_dict(check.get("repair_plan") or {})
    if not plan.codes:
        return None
    return sync_bars_repair(plan, sector=sector, job_id=job_id)


def sync_bars(
    *,
    sector: str = "沪深A股",
    start_date: Optional[str] = None,
    range_preset: Optional[str] = None,
    adjust_type: str = "front",
    incremental: bool = False,
    incremental_days: Optional[int] = None,
    mode: SyncMode = "incremental",
    repair_plan: Optional[RepairPlan | Dict[str, object]] = None,
    auto_repair: Optional[bool] = None,
    job_id: Optional[str] = None,
    resume_checkpoint: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    days = incremental_days if incremental_days is not None else settings.sync_incremental_days

    if mode == "repair" or repair_plan is not None:
        plan = (
            repair_plan
            if isinstance(repair_plan, RepairPlan)
            else RepairPlan.from_dict(repair_plan or {})
        )
        return sync_bars_repair(plan, sector=sector, job_id=job_id)

    processed_base = 0
    total_codes = 0
    if resume_checkpoint:
        codes: List[str] = list(resume_checkpoint.get("remaining_codes") or [])
        start = str(resume_checkpoint.get("start") or "")
        end = str(resume_checkpoint.get("end") or "")
        sector = str(resume_checkpoint.get("sector") or sector)
        adjust_type = str(resume_checkpoint.get("adjust_type") or adjust_type)
        effective_mode = str(resume_checkpoint.get("mode") or "incremental")
        processed_base = int(resume_checkpoint.get("processed") or 0)
        total_codes = int(resume_checkpoint.get("total") or (processed_base + len(codes)))
        if job_id:
            report_job_progress(
                job_id,
                0.05 + 0.90 * (processed_base / max(total_codes, 1)),
                f"续传同步（已完成 {processed_base}/{total_codes}）",
                step="sync",
                detail=f"{start} ~ {end}",
            )
    else:
        # Full-sync signals (incremental=False + start/range, or mode=full) must win over
        # the default mode="incremental", otherwise web/API full jobs run as ~5-day incremental.
        if incremental:
            start, end = (date.today() - timedelta(days=days)).isoformat(), date.today().isoformat()
            effective_mode: SyncMode = "incremental"
        elif start_date or range_preset or mode == "full":
            if start_date:
                start, end = start_date, date.today().isoformat()
            elif range_preset:
                start, end = resolve_range_preset(range_preset)
            else:
                start, end = resolve_range_preset("5y")
            effective_mode = "full"
        elif mode == "incremental":
            start, end = (date.today() - timedelta(days=days)).isoformat(), date.today().isoformat()
            effective_mode = "incremental"
        else:
            start, end = resolve_range_preset("5y")
            effective_mode = "full"

        if job_id:
            report_job_progress(
                job_id,
                0.06,
                "正在获取股票列表…",
                step="prepare",
                detail=f"{sector} · {effective_mode}",
            )
        if job_id and is_job_cancelled(job_id):
            raise JobCancelled(
                {
                    "remaining_codes": [],
                    "processed": 0,
                    "total": 0,
                    "start": start,
                    "end": end,
                    "sector": sector,
                    "adjust_type": adjust_type,
                    "mode": effective_mode,
                },
                progress=0.06,
                message="已中断（获取股票列表前）",
            )
        codes = resolve_universe(sector)
        total_codes = len(codes)
        if job_id:
            mode_label = "增量" if effective_mode == "incremental" else "全量"
            report_job_progress(
                job_id,
                0.08,
                sync_progress_message(
                    0,
                    total_codes,
                    job_id=job_id,
                    prefix=f"{mode_label}同步 {start} ~ {end}",
                    progress=0.08,
                ),
                step="sync",
                detail=f"共 {total_codes} 只股票 · 复权 {adjust_type}",
            )
        with db_session() as conn:
            record_universe_count(conn, sector, total_codes)
            ensure_instrument_codes(conn, codes)

    client = XtDataClient()
    dividend = DIVIDEND_MAP.get(adjust_type, "front")

    written = 0
    stock_error: Optional[BaseException] = None
    try:
        written = _fetch_and_upsert(
            client,
            codes,
            start,
            end,
            adjust_type,
            dividend,
            settings.sync_batch_size,
            job_id=job_id,
            processed_base=processed_base,
            total_codes=total_codes,
            sector=sector,
            mode=effective_mode,
        )
    except JobCancelled:
        raise
    except Exception as exc:
        stock_error = exc
    with db_session() as conn:
        market_latest = market_latest_date(conn, adjust_type)
        if market_latest:
            set_meta(conn, f"bars_market_latest:{adjust_type}", market_latest)

    try:
        sync_calendar_from_qmt(start_date=start, end_date=end)
    except Exception:
        sync_calendar_from_bars()

    names_backfilled = 0
    names_skipped = 0
    skip_names = effective_mode == "incremental" and not settings.sync_name_backfill_on_incremental
    if skip_names:
        with db_session() as conn:
            from qmt_quant.storage.instruments import count_missing_names

            names_skipped = count_missing_names(conn, codes)
        if job_id and names_skipped:
            report_job_progress(
                job_id,
                0.98,
                f"增量同步跳过名称补全（{names_skipped} 只待补全，请用数据页「补全股票名称」）",
                step="export" if settings.auto_export_catalog else "names",
                detail="名称与 K 线无关，不影响增量更新",
            )
    else:
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
        "sector": sector,
        "codes": total_codes,
        "start": start,
        "end": end,
        "mode": effective_mode,
        "adjust_type": adjust_type,
        "bars_written": written,
        "resumed_from": processed_base if resume_checkpoint else 0,
    }
    if names_backfilled:
        result["names_backfilled"] = names_backfilled
    if names_skipped:
        result["names_skipped"] = names_skipped
    if range_preset:
        result["range_preset"] = range_preset

    if settings.auto_export_catalog:
        if job_id:
            report_job_progress(job_id, 0.96, "导出验策略文件…", step="export")
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(
            adjust_type=adjust_type,
            codes=codes if effective_mode == "incremental" else None,
            job_id=job_id,
        )

    do_repair = settings.sync_auto_repair if auto_repair is None else auto_repair
    if not stock_error and do_repair and effective_mode == "incremental":
        repair_result = _maybe_auto_repair(
            sector=sector,
            adjust_type=adjust_type,
            incremental_days=days,
            job_id=job_id,
        )
        if repair_result:
            result["auto_repair"] = repair_result

    if written or result.get("auto_repair"):
        from qmt_quant.core.catalog.export import clear_price_matrix_cache
        from qmt_quant.core.data.query import clear_browse_query_cache
        from qmt_quant.core.sync.check import clear_data_check_cache

        clear_price_matrix_cache()
        clear_browse_query_cache()
        clear_data_check_cache()

    if stock_error:
        raise stock_error
    return result
