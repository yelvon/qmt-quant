"""Walk-forward analysis for research (BT-V-008)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import FEE_PRESETS
from qmt_quant.core.research.runner import _run_ma_cross_scan
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import save_backtest_run


def run_walk_forward(
    prices: pd.DataFrame,
    *,
    strategy_id: str = "ma_cross",
    short_preset: str = "preset_std",
    long_preset: str = "preset_std",
    train_bars: int = 252,
    test_bars: int = 63,
    step_bars: int | None = None,
    fees: float = 0.0003,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    if prices.empty or len(prices) < train_bars + test_bars:
        return {"error": "insufficient_data", "segments": []}

    step = step_bars or test_bars
    segments: List[Dict[str, Any]] = []
    idx = 0
    dates = list(prices.index)
    total_segments = max(1, (len(dates) - train_bars - test_bars) // step + 1)
    seg_no = 0

    while idx + train_bars + test_bars <= len(dates):
        train_end = idx + train_bars
        test_end = train_end + test_bars
        train_slice = prices.iloc[idx:train_end]
        test_slice = prices.iloc[train_end:test_end]

        if job_id:
            report_job_progress(
                job_id,
                0.25 + 0.6 * (seg_no / total_segments),
                f"Walk-Forward 段 {seg_no + 1}/{total_segments}",
                step="segment",
                detail=f"训练 {dates[idx].strftime('%Y-%m-%d')} ~ {dates[train_end - 1].strftime('%Y-%m-%d')}",
            )

        if strategy_id == "ma_cross":
            scan = _run_ma_cross_scan(train_slice, short_preset, long_preset, fees)
            best = scan.get("best") or {}
            short_w = int(best.get("short", 20))
            long_w = int(best.get("long", 120))
            is_ret = float(best.get("total_return_pct", 0))
            oos = _ma_oos_return(test_slice, short_w, long_w, fees)
        else:
            short_w, long_w, is_ret, oos = 20, 120, 0.0, 0.0

        segments.append(
            {
                "train_start": dates[idx].strftime("%Y-%m-%d"),
                "train_end": dates[train_end - 1].strftime("%Y-%m-%d"),
                "test_start": dates[train_end].strftime("%Y-%m-%d"),
                "test_end": dates[test_end - 1].strftime("%Y-%m-%d"),
                "short": short_w,
                "long": long_w,
                "is_return_pct": round(is_ret, 2),
                "oos_return_pct": round(oos * 100, 2),
            }
        )
        idx += step
        seg_no += 1

    positive = sum(1 for s in segments if s["oos_return_pct"] > 0)
    stability = round(positive / len(segments), 3) if segments else 0.0
    return {
        "strategy": strategy_id,
        "segments": segments,
        "stability_score": stability,
        "segment_count": len(segments),
    }


def _ma_oos_return(prices: pd.DataFrame, short_w: int, long_w: int, fees: float) -> float:
    fast = prices.rolling(short_w).mean()
    slow = prices.rolling(long_w).mean()
    signal = (fast > slow).astype(float)
    rets = prices.pct_change().fillna(0)
    strat_ret = (signal.shift(1) * rets).mean(axis=1)
    return float((1 + strat_ret).prod() - 1 - fees)


def run_walk_forward_study(
    *,
    strategy_id: str = "ma_cross",
    sector: str = "沪深A股",
    range_preset: str = "3y",
    short_preset: str = "preset_std",
    long_preset: str = "preset_std",
    fee_preset: str = "default",
    train_bars: int = 252,
    test_bars: int = 63,
    step_bars: int | None = None,
    codes: Optional[List[str]] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Load prices and run walk-forward analysis, persisting results."""
    run_migrations()
    settings = get_settings()
    start, end = resolve_range_preset(range_preset)
    if job_id:
        report_job_progress(
            job_id,
            0.12,
            "加载 Walk-Forward 数据…",
            step="load",
            detail=f"{start} ~ {end} · train {train_bars} / test {test_bars} 根 K 线",
        )
    if codes:
        universe = codes
    else:
        universe = resolve_universe(sector)[:50]
    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or None,
    )
    if prices.empty:
        return {"error": "no_price_data"}

    fees = FEE_PRESETS.get(fee_preset, FEE_PRESETS["default"])["commission_rate"]
    result = run_walk_forward(
        prices,
        strategy_id=strategy_id,
        short_preset=short_preset,
        long_preset=long_preset,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        fees=fees,
        job_id=job_id,
    )
    result["params"] = {
        "sector": sector,
        "range_preset": range_preset,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "codes": codes,
    }

    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    result_path = reports_dir / f"walk_forward_{strategy_id}_{range_preset}.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if job_id:
        report_job_progress(job_id, 0.92, "保存 Walk-Forward 结果…", step="save")

    with db_session() as conn:
        run_id = save_backtest_run(
            conn,
            engine="vectorbt",
            strategy_id=f"walk_forward_{strategy_id}",
            title=f"walk-forward {strategy_id} {range_preset}",
            params=result["params"],
            metrics={"stability_score": result.get("stability_score"), "segment_count": result.get("segment_count")},
            result_path=str(result_path),
        )
    result["run_id"] = run_id
    result["result_path"] = str(result_path)
    return result
