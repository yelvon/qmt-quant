"""Daily bar sync."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Literal, Optional

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.config import get_settings
from qmt_quant.core.presets import DIVIDEND_MAP, resolve_range_preset
from qmt_quant.core.sync.calendar import sync_calendar_from_bars, sync_calendar_from_qmt
from qmt_quant.core.sync.gaps import RepairPlan
from qmt_quant.core.sync.repair import _fetch_and_upsert, sync_bars_repair
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.bars import market_latest_date
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import set_meta


SyncMode = Literal["incremental", "full", "repair"]


def _maybe_auto_repair(
    *,
    sector: str,
    adjust_type: str,
    incremental_days: int,
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
    return sync_bars_repair(plan, sector=sector)


def sync_bars(
    *,
    sector: str = "沪深A股",
    start_date: Optional[str] = None,
    adjust_type: str = "front",
    incremental: bool = False,
    incremental_days: Optional[int] = None,
    mode: SyncMode = "incremental",
    repair_plan: Optional[RepairPlan | Dict[str, object]] = None,
    auto_repair: Optional[bool] = None,
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
        return sync_bars_repair(plan, sector=sector)

    if incremental or mode == "incremental":
        start, end = (date.today() - timedelta(days=days)).isoformat(), date.today().isoformat()
        effective_mode: SyncMode = "incremental"
    elif start_date:
        start, end = start_date, date.today().isoformat()
        effective_mode = "full"
    else:
        start, end = resolve_range_preset("5y")
        effective_mode = "full"

    codes = resolve_universe(sector)
    client = XtDataClient()
    dividend = DIVIDEND_MAP.get(adjust_type, "front")

    download_stats = client.download_history(
        codes,
        period="1d",
        start_time=to_qmt_date(start),
        end_time=to_qmt_date(end),
    )

    written = 0
    with db_session() as conn:
        written = _fetch_and_upsert(
            client,
            conn,
            codes,
            start,
            end,
            adjust_type,
            dividend,
            settings.sync_batch_size,
        )
        market_latest = market_latest_date(conn, adjust_type)
        if market_latest:
            set_meta(conn, f"bars_market_latest:{adjust_type}", market_latest)

    try:
        sync_calendar_from_qmt(start_date=start, end_date=end)
    except Exception:
        sync_calendar_from_bars()

    result: Dict[str, object] = {
        "sector": sector,
        "codes": len(codes),
        "start": start,
        "end": end,
        "mode": effective_mode,
        "adjust_type": adjust_type,
        "download_success": download_stats.success,
        "download_failed": download_stats.failed,
        "failed_codes": download_stats.failed_codes,
        "bars_written": written,
    }

    if settings.auto_export_catalog:
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(adjust_type=adjust_type)

    do_repair = settings.sync_auto_repair if auto_repair is None else auto_repair
    if do_repair and effective_mode == "incremental":
        repair_result = _maybe_auto_repair(
            sector=sector, adjust_type=adjust_type, incremental_days=days
        )
        if repair_result:
            result["auto_repair"] = repair_result

    return result
