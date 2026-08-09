"""Targeted bar gap repair."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import bars_from_dataframe
from qmt_quant.config import get_settings
from qmt_quant.core.sync.gaps import RepairPlan, analyze_gaps, build_repair_plan
from qmt_quant.core.sync.calendar import sync_calendar_from_bars, sync_calendar_from_qmt
from qmt_quant.storage.bars import market_latest_date, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import set_meta


def _fetch_and_upsert(
    client: XtDataClient,
    conn,
    codes: Sequence[str],
    start: str,
    end: str,
    adjust_type: str,
    dividend: str,
    batch_size: int,
) -> int:
    written = 0
    code_list = list(codes)
    for i in range(0, len(code_list), batch_size):
        chunk = code_list[i : i + batch_size]
        client.download_history(
            chunk,
            period="1d",
            start_time=to_qmt_date(start),
            end_time=to_qmt_date(end),
        )
        data = client.get_market_bars(
            chunk,
            period="1d",
            start_time=to_qmt_date(start),
            end_time=to_qmt_date(end),
            dividend_type=dividend,
        )
        for code, df in data.items():
            rows = bars_from_dataframe(code, df, adjust_type=adjust_type)
            written += upsert_bars(conn, rows)
    return written


def sync_bars_repair(
    plan: RepairPlan,
    *,
    sector: Optional[str] = None,
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
    with db_session() as conn:
        for dr in ranges:
            start, end = dr.get("start", ""), dr.get("end", "")
            if not start or not end:
                continue
            written += _fetch_and_upsert(
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
        sync_calendar_from_qmt(start_date=ranges[0].get("start"), end_date=ranges[0].get("end"))
    except Exception:
        sync_calendar_from_bars()

    result: Dict[str, object] = {
        "sector": sector or plan.sector,
        "codes": len(codes),
        "date_ranges": ranges,
        "bars_written": written,
        "adjust_type": adjust_type,
    }

    if settings.auto_export_catalog:
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(adjust_type=adjust_type)
    return result


def run_check_and_repair(
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    detailed: bool = True,
    codes: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    check = analyze_gaps(sector=sector, adjust_type=adjust_type, detailed=detailed)
    if not check.get("needs_repair") and not codes:
        return {"check": check, "repair": {"skipped": True, "reason": "no repair needed"}}

    if codes:
        plan = build_repair_plan(sector=sector, adjust_type=adjust_type, codes=list(codes))
    else:
        plan = RepairPlan.from_dict(check.get("repair_plan") or {})
    repair = sync_bars_repair(plan, sector=sector)
    post_check = analyze_gaps(sector=sector, adjust_type=adjust_type, detailed=detailed)
    return {"check": check, "repair": repair, "post_check": post_check}
