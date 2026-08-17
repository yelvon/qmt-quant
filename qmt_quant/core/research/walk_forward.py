"""Walk-forward analysis for research (BT-V-008)."""

from __future__ import annotations

import json
from math import sqrt
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.backtest.strategy import STRATEGIES, CostModel, PortfolioSpec
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.data.frequency import BarFrequency
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import FEE_PRESETS, ma_param_combos
from qmt_quant.core.research.universe import resolve_research_universe_meta
from qmt_quant.core.validation.backtester import AShareDailyBacktester
from qmt_quant.core.universe import mask_prices_by_lifecycle
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
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
    window_type: str = "rolling",
    purge_bars: int = 0,
    embargo_bars: int = 0,
    strategy_params: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    frequency = BarFrequency.parse(bar_frequency)
    if window_type not in {"rolling", "expanding"}:
        raise ValueError("window_type must be rolling or expanding")
    if min(train_bars, test_bars) <= 0 or min(purge_bars, embargo_bars) < 0:
        raise ValueError("bar counts must be non-negative and train/test positive")
    if prices.empty or len(prices) < train_bars + purge_bars + embargo_bars + test_bars:
        return {"error": "insufficient_data", "segments": []}

    plugin = STRATEGIES.get(strategy_id)
    candidate_options = dict(strategy_params or {})
    candidates = list(plugin.candidate_params(candidate_options))
    if strategy_id == "ma_cross" and not strategy_params:
        candidates = [
            {"short_window": short, "long_window": long}
            for short, long in ma_param_combos(short_preset, long_preset)
        ]
    if not candidates:
        return {"error": "no_candidate_params", "segments": []}
    step = step_bars or test_bars
    if step <= 0:
        raise ValueError("step_bars must be positive")
    segments: List[Dict[str, Any]] = []
    oos_returns: List[pd.Series] = []
    previous_params: Optional[Dict[str, Any]] = None
    origin = 0
    dates = list(prices.index)
    required = train_bars + purge_bars + embargo_bars + test_bars
    total_segments = max(1, (len(dates) - required) // step + 1)
    seg_no = 0

    while origin + required <= len(dates):
        raw_train_end = origin + train_bars
        train_end = raw_train_end - purge_bars
        test_start = raw_train_end + embargo_bars
        test_end = test_start + test_bars
        train_start = 0 if window_type == "expanding" else origin
        train_slice = prices.iloc[train_start:train_end]
        test_slice = prices.iloc[test_start:test_end]

        if job_id:
            report_job_progress(
                job_id,
                0.25 + 0.6 * (seg_no / total_segments),
                f"Walk-Forward 段 {seg_no + 1}/{total_segments}",
                step="segment",
                detail=f"训练 {dates[train_start].strftime('%Y-%m-%d')} ~ {dates[train_end - 1].strftime('%Y-%m-%d')}",
            )

        scored = [
            (_kernel_run(train_slice, train_slice, strategy_id, params, fees, metadata), params)
            for params in candidates
        ]
        is_result, best_params = max(scored, key=lambda item: item[0]["total_return_pct"])
        # The signal context may include history for indicator warm-up, while
        # execution and capital accounting are strictly limited to OOS bars.
        signal_history = prices.iloc[train_start:test_end]
        oos_result = _kernel_run(
            test_slice, signal_history, strategy_id, best_params, fees, metadata
        )
        segment_returns = _returns_from_equity(oos_result["equity_curve"])
        if oos_returns:
            seen = pd.concat(oos_returns).index
            segment_returns = segment_returns[~segment_returns.index.isin(seen)]
        if not segment_returns.empty:
            oos_returns.append(segment_returns)
        drift = _parameter_distance(previous_params, best_params)
        previous_params = dict(best_params)
        is_ret = float(is_result["total_return_pct"])
        oos_ret = float(oos_result["total_return_pct"])

        segments.append(
            {
                "train_start": dates[train_start].strftime("%Y-%m-%d"),
                "train_end": dates[train_end - 1].strftime("%Y-%m-%d"),
                "test_start": dates[test_start].strftime("%Y-%m-%d"),
                "test_end": dates[test_end - 1].strftime("%Y-%m-%d"),
                "params": dict(best_params),
                "is_return_pct": round(is_ret, 2),
                "oos_return_pct": round(oos_ret, 2),
                "decay_pct": round(oos_ret - is_ret, 2),
                "parameter_drift": drift,
            }
        )
        # Preserve legacy MA fields consumed by old clients.
        if strategy_id == "ma_cross":
            segments[-1]["short"] = int(best_params["short_window"])
            segments[-1]["long"] = int(best_params["long_window"])
        if strategy_id == "macd_cross":
            segments[-1]["fast"] = int(best_params["fast_window"])
            segments[-1]["slow"] = int(best_params["slow_window"])
            segments[-1]["signal"] = int(best_params["signal_window"])
        origin += step
        seg_no += 1

    positive = sum(1 for s in segments if s["oos_return_pct"] > 0)
    stability = round(positive / len(segments), 3) if segments else 0.0
    joined = pd.concat(oos_returns).sort_index() if oos_returns else pd.Series(dtype=float)
    equity = (1 + joined).cumprod()
    annual = 52 if frequency is BarFrequency.WEEKLY else 252
    sharpe = float(joined.mean() / joined.std(ddof=1) * sqrt(annual)) if len(joined) > 1 and joined.std(ddof=1) > 0 else 0.0
    drawdown = equity / equity.cummax() - 1 if not equity.empty else pd.Series(dtype=float)
    mean_is = float(np.mean([s["is_return_pct"] for s in segments])) if segments else 0.0
    mean_oos = float(np.mean([s["oos_return_pct"] for s in segments])) if segments else 0.0
    return {
        "strategy": strategy_id,
        "segments": segments,
        "stability_score": stability,
        "segment_count": len(segments),
        "window_type": window_type,
        "purge_bars": purge_bars,
        "embargo_bars": embargo_bars,
        "is_mean_return_pct": round(mean_is, 4),
        "oos_mean_return_pct": round(mean_oos, 4),
        "is_oos_decay_pct": round(mean_oos - mean_is, 4),
        "oos_sharpe": round(sharpe, 4),
        "oos_max_drawdown_pct": round(float(drawdown.min()) * 100, 4) if not drawdown.empty else 0.0,
        "parameter_drift": {
            "mean_distance": round(float(np.mean([s["parameter_drift"] for s in segments[1:]])), 4) if len(segments) > 1 else 0.0,
            "changes": sum(1 for s in segments[1:] if s["parameter_drift"] > 0),
        },
        "oos_equity_curve": [
            {"date": date.strftime("%Y-%m-%d"), "equity": round(float(value) * 100, 8)}
            for date, value in equity.items()
        ],
    }


def _kernel_run(
    execution_prices: pd.DataFrame,
    signal_prices: pd.DataFrame,
    strategy_id: str,
    params: Dict[str, Any],
    fees: float,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    base = CostModel.from_settings()
    engine = AShareDailyBacktester(
        execution_prices,
        signal_prices=signal_prices,
        cost_model=CostModel(
            commission_rate=fees,
            min_commission=base.min_commission,
            stamp_duty_rate=base.stamp_duty_rate,
            transfer_fee_rate=base.transfer_fee_rate,
            slippage_bps=base.slippage_bps,
        ),
        portfolio=PortfolioSpec.for_universe(len(execution_prices.columns)),
    )
    result = engine.run_strategy(strategy_id, params, metadata=metadata)
    return {
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "equity_curve": result.equity_curve,
    }


def _returns_from_equity(curve: List[Dict[str, Any]]) -> pd.Series:
    if not curve:
        return pd.Series(dtype=float)
    values = pd.Series(
        [float(row["equity"]) / 100 for row in curve],
        index=pd.to_datetime([row["date"] for row in curve]),
        dtype=float,
    )
    return values.pct_change().fillna(values.iloc[0] - 1)


def _parameter_distance(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> float:
    if previous is None:
        return 0.0
    keys = sorted(set(previous) | set(current))
    distances = []
    for key in keys:
        left, right = previous.get(key), current.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            scale = max(abs(float(left)), abs(float(right)), 1.0)
            distances.append(abs(float(right) - float(left)) / scale)
        else:
            distances.append(float(left != right))
    return round(float(np.mean(distances)), 6) if distances else 0.0


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
    sample: str = "all",
    universe_n: Optional[int] = None,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
    window_type: str = "rolling",
    purge_bars: int = 0,
    embargo_bars: int = 0,
    strategy_params: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Load prices and run walk-forward analysis, persisting results."""
    run_migrations()
    settings = get_settings()
    frequency = BarFrequency.parse(bar_frequency)
    start, end = resolve_range_preset(range_preset)
    if job_id:
        report_job_progress(
            job_id,
            0.12,
            "加载 Walk-Forward 数据…",
            step="load",
            detail=f"{start} ~ {end} · train {train_bars} / test {test_bars} 根 K 线",
        )
    universe, uni_meta = resolve_research_universe_meta(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        sample=sample,
        universe_n=universe_n,
        range_start=start,
        range_end=end,
        adjust_type=settings.bar_adjust_type,
    )
    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or None,
        bar_frequency=frequency,
    )
    prices = mask_prices_by_lifecycle(prices)
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
        bar_frequency=frequency,
        window_type=window_type,
        purge_bars=purge_bars,
        embargo_bars=embargo_bars,
        strategy_params=strategy_params,
        job_id=job_id,
    )
    used_codes = list(prices.columns)
    result["params"] = {
        "sector": sector,
        "range_preset": range_preset,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "codes": used_codes,
        "sample": uni_meta.get("sample") or sample,
        "universe_n": uni_meta.get("universe_n"),
        "bar_frequency": frequency.value,
        "bar_unit": frequency.value,
        "window_type": window_type,
        "purge_bars": purge_bars,
        "embargo_bars": embargo_bars,
        "strategy_params": strategy_params or {},
        "short_preset": short_preset,
        "long_preset": long_preset,
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
            metrics={
                "stability_score": result.get("stability_score"),
                "segment_count": result.get("segment_count"),
                "oos_sharpe": result.get("oos_sharpe"),
                "oos_max_drawdown_pct": result.get("oos_max_drawdown_pct"),
                "is_oos_decay_pct": result.get("is_oos_decay_pct"),
            },
            result_path=str(result_path),
            job_id=job_id,
            run_kind="walk_forward",
        )
    result["run_id"] = run_id
    result["result_path"] = str(result_path)
    return result
