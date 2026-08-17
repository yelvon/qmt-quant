"""VectorBT research runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import FEE_PRESETS, ma_param_combos
from qmt_quant.core.research.report import build_quantstats_summary
from qmt_quant.core.research.universe import resolve_research_universe
from qmt_quant.core.screener.bridge import load_codes_by_run_id
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import save_backtest_run


def _research_title(strategy_id: str, range_preset: str, codes: Optional[List[str]]) -> str:
    if codes and len(codes) == 1:
        return f"{strategy_id} {codes[0]} {range_preset}"
    return f"{strategy_id} {range_preset}"


def run_research(
    *,
    strategy_id: str = "ma_cross",
    sector: str = "沪深A股",
    range_preset: str = "3y",
    short_preset: str = "preset_std",
    long_preset: str = "preset_std",
    fee_preset: str = "default",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    settings = get_settings()
    if job_id:
        report_job_progress(
            job_id,
            0.08,
            "加载行情数据…",
            step="load",
            detail=f"策略 {strategy_id} · 区间 {range_preset}",
        )
    start, end = resolve_range_preset(range_preset)
    load_codes = resolve_research_universe(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
    )

    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=load_codes if load_codes else None,
    )
    if prices.empty:
        return {"error": "no_price_data", "message": "请先同步日线数据"}

    n_codes = len(prices.columns)
    n_days = len(prices.index)
    if job_id:
        report_job_progress(
            job_id,
            0.18,
            f"行情已加载 · {n_codes} 只股票 · {n_days} 个交易日",
            step="load",
            detail=f"{start} ~ {end}",
        )

    fees = FEE_PRESETS.get(fee_preset, FEE_PRESETS["default"])["commission_rate"]

    if strategy_id == "ma_cross":
        result = _run_ma_cross_scan(prices, short_preset, long_preset, fees, job_id=job_id)
    elif strategy_id == "buy_hold":
        if job_id:
            report_job_progress(job_id, 0.45, "运行买入持有基准…", step="scan")
        result = _run_buy_hold(prices, fees)
    elif strategy_id == "pe_momentum":
        if job_id:
            report_job_progress(job_id, 0.45, "运行低估值动量策略…", step="scan")
        result = _run_pe_momentum(prices, fees)
    elif strategy_id == "screening_rebalance":
        if job_id:
            report_job_progress(job_id, 0.45, "运行选股池再平衡…", step="scan")
        result = _run_screening_rebalance(prices, fees, screen_run_id)
    else:
        result = _run_ma_cross_scan(prices, short_preset, long_preset, fees, job_id=job_id)

    equity_map = _equity_from_result(result, prices)
    result["quantstats"] = build_quantstats_summary(equity_map)
    result["best"]["quantstats"] = result["quantstats"]
    used_codes = list(prices.columns)
    result["universe_codes"] = used_codes

    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    label = result["best"].get("label", strategy_id).replace("/", "_")
    result_path = reports_dir / f"research_{label}.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if job_id:
        report_job_progress(job_id, 0.88, "保存回测结果…", step="save")

    with db_session() as conn:
        run_id = save_backtest_run(
            conn,
            engine="vectorbt",
            strategy_id=strategy_id,
            title=_research_title(strategy_id, range_preset, used_codes if len(used_codes) == 1 else codes),
            params={
                "sector": sector,
                "range_preset": range_preset,
                "short_preset": short_preset,
                "long_preset": long_preset,
                "fee_preset": fee_preset,
                "screen_run_id": screen_run_id,
                "codes": used_codes,
            },
            metrics=result["best"],
            result_path=str(result_path),
        )
    result["run_id"] = run_id
    result["result_path"] = str(result_path)
    result["universe_used"] = len(used_codes)
    return result


def _equity_from_result(result: Dict[str, Any], prices: pd.DataFrame) -> Dict[str, float]:
    if result.get("equity_curve"):
        return {e["date"]: e["equity"] / 100 for e in result["equity_curve"]}
    rets = prices.pct_change().fillna(0).mean(axis=1)
    equity = (1 + rets).cumprod()
    return {dt.strftime("%Y-%m-%d"): float(v) for dt, v in equity.items()}


def _run_ma_cross_scan(
    prices: pd.DataFrame,
    short_preset: str,
    long_preset: str,
    fees: float,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    combos = ma_param_combos(short_preset, long_preset)
    rows: List[Dict[str, Any]] = []
    total = len(combos)

    try:
        import vectorbt as vbt

        for idx, (short_w, long_w) in enumerate(combos):
            if job_id and (idx == 0 or idx % 2 == 0 or idx == total - 1):
                report_job_progress(
                    job_id,
                    0.22 + 0.58 * (idx / max(total, 1)),
                    f"参数扫描 {idx + 1}/{total}",
                    step="scan",
                    detail=f"组合 {short_w}/{long_w}",
                )
            fast = vbt.MA.run(prices, short_w, short_name="fast")
            slow = vbt.MA.run(prices, long_w, short_name="slow")
            entries = fast.ma_crossed_above(slow)
            exits = fast.ma_crossed_below(slow)
            pf = vbt.Portfolio.from_signals(
                prices,
                entries,
                exits,
                fees=fees,
                freq="1D",
                cash_sharing=True,
            )
            total_return = float(pf.total_return().mean())
            rows.append(
                {
                    "short": short_w,
                    "long": long_w,
                    "label": f"{short_w}/{long_w}",
                    "total_return_pct": round(total_return * 100, 2),
                }
            )
    except ImportError:
        for idx, (short_w, long_w) in enumerate(combos):
            if job_id and (idx == 0 or idx % 3 == 0 or idx == total - 1):
                report_job_progress(
                    job_id,
                    0.22 + 0.58 * (idx / max(total, 1)),
                    f"参数扫描 {idx + 1}/{total}",
                    step="scan",
                    detail=f"组合 {short_w}/{long_w}",
                )
        rows = _numpy_ma_scan(prices, combos, fees)

    rows.sort(key=lambda r: r["total_return_pct"], reverse=True)
    best = rows[0] if rows else {"label": "n/a", "total_return_pct": 0}
    return {"strategy": "ma_cross", "combos": rows, "best": best, "engine": "vectorbt"}


def _numpy_ma_scan(
    prices: pd.DataFrame,
    combos: List[Tuple[int, int]],
    fees: float,
) -> List[Dict[str, Any]]:
    rows = []
    for short_w, long_w in combos:
        fast = prices.rolling(short_w).mean()
        slow = prices.rolling(long_w).mean()
        signal = (fast > slow).astype(float)
        rets = prices.pct_change().fillna(0)
        strat_ret = (signal.shift(1) * rets).mean(axis=1)
        total = float((1 + strat_ret).prod() - 1 - fees)
        rows.append(
            {
                "short": short_w,
                "long": long_w,
                "label": f"{short_w}/{long_w}",
                "total_return_pct": round(total * 100, 2),
            }
        )
    return rows


def _run_buy_hold(prices: pd.DataFrame, fees: float) -> Dict[str, Any]:
    rets = prices.pct_change().fillna(0).mean(axis=1)
    total = float((1 + rets).prod() - 1 - fees)
    best = {"label": "buy_hold", "total_return_pct": round(total * 100, 2)}
    return {"strategy": "buy_hold", "combos": [best], "best": best, "engine": "vectorbt"}


def _run_pe_momentum(prices: pd.DataFrame, fees: float) -> Dict[str, Any]:
    from qmt_quant.core.research.factors import load_pe_matrix

    with db_session() as conn:
        pe_mat = load_pe_matrix(conn, prices.index, list(prices.columns))
    mom = prices.pct_change(20)
    signal = ((pe_mat <= 30) & (mom > 0)).astype(float)
    rets = prices.pct_change().fillna(0)
    strat_ret = (signal.shift(1) * rets).mean(axis=1)
    total = float((1 + strat_ret).prod() - 1 - fees)
    best = {"label": "pe_momentum", "total_return_pct": round(total * 100, 2)}
    return {"strategy": "pe_momentum", "combos": [best], "best": best, "engine": "vectorbt"}


def _run_screening_rebalance(
    prices: pd.DataFrame,
    fees: float,
    screen_run_id: Optional[str],
) -> Dict[str, Any]:
    codes = load_codes_by_run_id(screen_run_id) if screen_run_id else []
    valid = [c for c in codes if c in prices.columns]
    if not valid:
        return {
            "strategy": "screening_rebalance",
            "combos": [],
            "best": {"label": "screening_rebalance", "total_return_pct": 0},
            "engine": "vectorbt",
            "error": "no_screen_codes",
        }
    subset = prices[valid]
    rets = subset.pct_change().fillna(0).mean(axis=1)
    total = float((1 + rets).prod() - 1 - fees)
    best = {"label": "screening_rebalance", "total_return_pct": round(total * 100, 2)}
    return {"strategy": "screening_rebalance", "combos": [best], "best": best, "engine": "vectorbt"}
