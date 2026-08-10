"""Data health checks."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from qmt_quant.config import get_settings
from qmt_quant.core.sync.gaps import analyze_gaps
from qmt_quant.core.ttl_cache import TtlCache
from qmt_quant.storage.bars import coverage_stats, quality_stats
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import set_meta_json

_DATA_CHECK_CACHE: TtlCache[Dict[str, object]] = TtlCache(ttl_seconds=20.0)


def clear_data_check_cache() -> None:
    _DATA_CHECK_CACHE.clear()


def run_data_check(
    *,
    as_of_date: Optional[str] = None,
    adjust_type: str = "front",
    sector: str = "沪深A股",
    detailed: bool = False,
    include_repair_plan: bool = False,
    use_cache: bool = True,
) -> Dict[str, object]:
    as_of = as_of_date or date.today().isoformat()
    cache_key = (sector, adjust_type, detailed, include_repair_plan, as_of)
    if use_cache:
        cached = _DATA_CHECK_CACHE.get(cache_key)
        if cached is not None:
            return cached

    result = _run_data_check_uncached(
        as_of_date=as_of,
        adjust_type=adjust_type,
        sector=sector,
        detailed=detailed,
        include_repair_plan=include_repair_plan,
    )
    if use_cache:
        _DATA_CHECK_CACHE.set(cache_key, result)
    return result


def _run_data_check_uncached(
    *,
    as_of_date: str,
    adjust_type: str,
    sector: str,
    detailed: bool,
    include_repair_plan: bool,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    adjust = adjust_type or settings.bar_adjust_type

    gap_info = analyze_gaps(
        sector=sector,
        adjust_type=adjust,
        detailed=detailed,
        as_of_date=as_of_date,
        include_repair_plan=include_repair_plan,
    )

    with db_session() as conn:
        cov = coverage_stats(conn, adjust_type=adjust)
        checks: List[Dict[str, object]] = []

        bar_codes = int(gap_info.get("bar_codes_with_data") or cov.get("codes", 0) or 0)
        universe_total = int(gap_info.get("universe_total") or bar_codes or 1)
        universe_estimated = bool(gap_info.get("universe_estimated"))
        coverage_pct = float(gap_info.get("bar_coverage_pct", 0) or 0)
        if universe_estimated:
            detail = f"{bar_codes} 只股票有日线（股票池规模未知，请先同步）"
            coverage_label = "—"
            line_ok = False
        else:
            detail = f"{bar_codes}/{universe_total} 只股票有日线"
            coverage_label = f"{coverage_pct}%"
            line_ok = coverage_pct >= 90
        checks.append(
            {
                "name": "日线是否齐全",
                "ok": line_ok,
                "coverage": coverage_label,
                "detail": detail,
            }
        )

        freshness = gap_info.get("freshness") or {}
        lag_days = int(freshness.get("lag_days", 0) or 0)
        market_latest = freshness.get("market_latest")
        checks.append(
            {
                "name": "市场新鲜度",
                "ok": lag_days <= 1,
                "coverage": f"滞后 {lag_days} 交易日",
                "detail": f"最新行情 {market_latest or '—'}",
            }
        )

        gap_summary = gap_info.get("gap_summary") or {}
        stale_pct = float(gap_summary.get("stale_pct", 0) or 0)
        stale_count = int(gap_summary.get("stale_count", 0) or 0)
        checks.append(
            {
                "name": "个股滞后",
                "ok": stale_pct < 5.0,
                "coverage": f"{stale_pct}%",
                "detail": f"{stale_count} 只股票落后市场",
            }
        )

        missing_market = gap_summary.get("missing_market_dates") or []
        checks.append(
            {
                "name": "市场缺日",
                "ok": len(missing_market) == 0,
                "coverage": "—",
                "detail": f"近30日缺 {len(missing_market)} 个交易日",
            }
        )

        if detailed:
            completeness = float(gap_summary.get("completeness_median", 0) or 0)
            checks.append(
                {
                    "name": "区间完整度",
                    "ok": completeness >= settings.sync_completeness_threshold,
                    "coverage": f"{round(completeness * 100, 1)}%",
                    "detail": f"抽样中位完整度（阈值 {settings.sync_completeness_threshold:.0%}）",
                }
            )

        cal_count = conn.execute("SELECT COUNT(*) FROM trade_calendar").fetchone()[0]
        checks.append(
            {
                "name": "交易日历",
                "ok": cal_count > 0,
                "coverage": "100%" if cal_count else "0%",
                "detail": f"{cal_count} 个交易日记录",
            }
        )

        fin_count = conn.execute(
            "SELECT COUNT(*) FROM financial_pershareindex"
        ).fetchone()[0]
        checks.append(
            {
                "name": "财务披露",
                "ok": fin_count > 0,
                "coverage": "—",
                "detail": f"{fin_count} 条每股指标",
            }
        )

        qstats = quality_stats(conn, adjust_type=adjust)
        checks.append(
            {
                "name": "数据质量",
                "ok": qstats["suspicious_pct"] < 5,
                "coverage": f"{100 - qstats['suspicious_pct']}%",
                "detail": f"bad={qstats['bad_bars_count']}, suspicious={qstats['suspicious_bars_count']}",
            }
        )

        set_meta_json(
            conn,
            f"last_gap_scan:{sector}",
            {
                "as_of": as_of_date,
                "needs_repair": gap_info.get("needs_repair"),
                "stale_count": stale_count,
            },
        )

        needs_repair = bool(gap_info.get("needs_repair"))
        summary_ok = all(c["ok"] for c in checks[:4]) and not needs_repair

        return {
            "as_of": as_of_date,
            "adjust_type": adjust,
            "checks": checks,
            "bar_coverage_pct": coverage_pct,
            "universe_total": universe_total,
            "universe_estimated": universe_estimated,
            "quality": qstats,
            "freshness": freshness,
            "stale_codes": gap_info.get("stale_codes") or [],
            "gap_summary": gap_summary,
            "repair_plan": gap_info.get("repair_plan"),
            "needs_repair": needs_repair,
            "summary_ok": summary_ok,
        }
