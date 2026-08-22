"""Data health checks."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from qmt_quant.config import get_settings
from qmt_quant.core.data.query import get_date_range
from qmt_quant.core.sync.gaps import analyze_gaps
from qmt_quant.core.ttl_cache import TtlCache
from qmt_quant.storage.bars import quality_stats
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.sync_meta import get_meta, get_meta_json, set_meta_json

_DATA_CHECK_CACHE: TtlCache[Dict[str, object]] = TtlCache(ttl_seconds=300.0)
_SUMMARY_CACHE: TtlCache[Dict[str, object]] = TtlCache(ttl_seconds=60.0)


def clear_data_check_cache() -> None:
    _DATA_CHECK_CACHE.clear()
    _SUMMARY_CACHE.clear()


def run_data_summary(
    *,
    adjust_type: str = "front",
    sector: str = "沪深A股",
    use_cache: bool = True,
) -> Dict[str, object]:
    """Lightweight local data snapshot for page header (no gap scan)."""
    settings = get_settings()
    adjust = adjust_type or settings.bar_adjust_type
    cache_key = (sector, adjust)
    if use_cache:
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached is not None:
            return cached

    run_migrations()
    with db_session() as conn:
        from qmt_quant.core.sync.universe_stats import resolve_universe_total
        from qmt_quant.storage.bars import distinct_code_count

        bar_range = get_date_range(conn, adjust)
        bar_codes = distinct_code_count(conn, adjust)
        universe_total, universe_estimated = resolve_universe_total(
            conn, sector, bar_codes=bar_codes
        )
        coverage_pct = 0.0
        if not universe_estimated and universe_total:
            coverage_pct = round(min(100.0, bar_codes / universe_total * 100), 1)

        fin_stats = conn.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT code), MAX(announce_date)
            FROM financial_pershareindex
            WHERE announce_date IS NOT NULL
            """
        ).fetchone()
        fin_count = int(fin_stats[0] or 0) if fin_stats else 0
        fin_codes = int(fin_stats[1] or 0) if fin_stats else 0
        fin_announce_max = (
            str(fin_stats[2])[:10] if fin_stats and fin_stats[2] else None
        )
        fin_watermark = get_meta(conn, f"financial_watermark:{sector}")
        if fin_watermark:
            fin_watermark = fin_watermark[:10]

        last_scan = get_meta_json(conn, f"last_gap_scan:{sector}")
        from qmt_quant.storage.index_bars import index_coverage_stats

        index_stats = index_coverage_stats(conn)

    result: Dict[str, object] = {
        "adjust_type": adjust,
        "sector": sector,
        "bar_date_min": bar_range.get("min_date"),
        "bar_date_max": bar_range.get("max_date"),
        "bar_codes_count": bar_codes,
        "bar_coverage_pct": coverage_pct,
        "universe_total": universe_total,
        "universe_estimated": universe_estimated,
        "financial_row_count": fin_count,
        "financial_codes_count": fin_codes,
        "financial_announce_max": fin_announce_max,
        "financial_watermark": fin_watermark,
        "last_health_scan": last_scan,
        **index_stats,
    }
    if use_cache:
        _SUMMARY_CACHE.set(cache_key, result)
    return result


def run_data_check(
    *,
    as_of_date: Optional[str] = None,
    adjust_type: str = "front",
    sector: str = "沪深A股",
    detailed: bool = False,
    include_repair_plan: bool = False,
    use_cache: bool = True,
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    as_of = as_of_date or date.today().isoformat()
    if job_id:
        use_cache = False
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
        job_id=job_id,
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
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    from qmt_quant.core.jobs.context import report_job_progress

    run_migrations()
    settings = get_settings()
    adjust = adjust_type or settings.bar_adjust_type

    if job_id:
        report_job_progress(
            job_id,
            0.05,
            "准备数据健康检查…",
            step="prepare",
            step_label="准备",
        )

    gap_info = analyze_gaps(
        sector=sector,
        adjust_type=adjust,
        detailed=detailed,
        as_of_date=as_of_date,
        include_repair_plan=include_repair_plan,
        job_id=job_id,
    )

    if job_id:
        report_job_progress(job_id, 0.76, "汇总检查项…", step="aggregate", step_label="汇总")

    with db_session() as conn:
        checks: List[Dict[str, object]] = []

        bar_codes = int(gap_info.get("bar_codes_with_data") or 0)
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
            skipped = bool(gap_summary.get("completeness_skipped"))
            checks.append(
                {
                    "name": "区间完整度",
                    "ok": skipped or completeness >= settings.sync_completeness_threshold,
                    "coverage": "—" if skipped else f"{round(completeness * 100, 1)}%",
                    "detail": "无滞后个股，未抽样"
                    if skipped
                    else f"抽样中位完整度（阈值 {settings.sync_completeness_threshold:.0%}）",
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

        fin_stats = conn.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT code), MAX(announce_date)
            FROM financial_pershareindex
            WHERE announce_date IS NOT NULL
            """
        ).fetchone()
        fin_count = int(fin_stats[0] or 0) if fin_stats else 0
        fin_codes = int(fin_stats[1] or 0) if fin_stats else 0
        fin_announce_max = (
            str(fin_stats[2])[:10] if fin_stats and fin_stats[2] else None
        )
        fin_watermark = get_meta(conn, f"financial_watermark:{sector}")
        if fin_watermark:
            fin_watermark = fin_watermark[:10]
        checks.append(
            {
                "name": "财务披露",
                "ok": fin_count > 0,
                "coverage": "—",
                "detail": f"{fin_count} 条每股指标（{fin_codes} 只）",
            }
        )

        qstats: Dict[str, object] = {}
        if detailed:
            if job_id:
                report_job_progress(
                    job_id,
                    0.84,
                    "统计数据质量（全库扫描，较慢）…",
                    step="quality",
                    step_label="数据质量",
                )
            qstats = quality_stats(conn, adjust_type=adjust)
            suspicious_pct = float(qstats.get("suspicious_pct", 0) or 0)
            checks.append(
                {
                    "name": "数据质量",
                    "ok": suspicious_pct < 5,
                    "coverage": f"{100 - suspicious_pct:.1f}%",
                    "detail": (
                        f"bad={qstats['bad_bars_count']}, suspicious={qstats['suspicious_bars_count']} "
                        f"（suspicious 多为成交量=0 的停牌/旧数据，全量历史库常见）"
                    ),
                }
            )

        bar_range = get_date_range(conn, adjust)

        if job_id:
            report_job_progress(job_id, 0.94, "保存检查结果…", step="save", step_label="保存")

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
            "bar_date_min": bar_range.get("min_date"),
            "bar_date_max": bar_range.get("max_date"),
            "financial_row_count": fin_count,
            "financial_codes_count": fin_codes,
            "financial_announce_max": fin_announce_max,
            "financial_watermark": fin_watermark,
            "freshness": freshness,
            "stale_codes": gap_info.get("stale_codes") or [],
            "gap_summary": gap_summary,
            "repair_plan": gap_info.get("repair_plan"),
            "needs_repair": needs_repair,
            "summary_ok": summary_ok,
        }
