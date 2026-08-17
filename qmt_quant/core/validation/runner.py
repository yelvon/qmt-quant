"""Validation runner and comparison with research."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.backtest.strategy import CostModel, PortfolioSpec
from qmt_quant.core.backtest.experiments import (
    build_diagnostics,
    compute_metrics,
    data_fingerprint,
    strategy_identity,
    write_artifacts,
)
from qmt_quant.core.catalog.export import load_ohlcv_df, load_price_matrix
from qmt_quant.core.data.frequency import BarFrequency
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.report import build_quantstats_summary
from qmt_quant.core.research.universe import universe_from_research_run
from qmt_quant.core.validation.compare import compare_with_research
from qmt_quant.core.validation.engine import get_validation_engine, validation_engine_display_name, validation_engine_label
from qmt_quant.core.validation.per_stock import compute_per_stock_returns
from qmt_quant.core.validation.trades import serialize_trades
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import get_backtest_run, new_id, save_backtest_run


def run_validation(
    *,
    from_run_id: Optional[str] = None,
    strategy_id: str = "ma_cross",
    short_window: int = 20,
    long_window: int = 120,
    fast_window: int = 12,
    slow_window: int = 26,
    signal_window: int = 9,
    match_price: str = "next_open",
    benchmark: str = "hs300",
    range_preset: str = "3y",
    screen_run_id: Optional[str] = None,
    codes: Optional[list[str]] = None,
    engine: Optional[str] = None,
    signals: Optional[list] = None,
    sample: str = "all",
    universe_n: Optional[int] = None,
    bar_frequency: BarFrequency | str | None = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    settings = get_settings()
    if job_id:
        report_job_progress(job_id, 0.1, "读取扫描参数…", step="load")
    research_metrics = None
    research_row: Optional[dict] = None
    fee_preset = "default"
    universe = list(codes) if codes else None
    inherited_frequency: str | None = None
    if from_run_id:
        with db_session() as conn:
            research_row = get_backtest_run(conn, from_run_id)
        if research_row:
            research_metrics = research_row.get("metrics")
            params = research_row.get("params", {})
            best = research_metrics or {}
            strategy_id = research_row.get("strategy_id", strategy_id)
            label = best.get("label", "20/120")
            if strategy_id == "ma_cross" and "/" in str(label):
                parts = str(label).split("/")
                if len(parts) >= 2:
                    short_window = int(parts[0])
                    long_window = int(parts[1])
            if strategy_id == "macd_cross":
                fast_window = int(best.get("fast_window", params.get("fast_window", fast_window)))
                slow_window = int(best.get("slow_window", params.get("slow_window", slow_window)))
                signal_window = int(
                    best.get("signal_window", params.get("signal_window", signal_window))
                )
                parts = str(label).split("/")
                if len(parts) == 3:
                    fast_window = int(parts[0])
                    slow_window = int(parts[1])
                    signal_window = int(parts[2])
            range_preset = params.get("range_preset", range_preset)
            screen_run_id = params.get("screen_run_id", screen_run_id)
            fee_preset = params.get("fee_preset", fee_preset)
            inherited_frequency = params.get("bar_frequency")
            resolved = universe_from_research_run(research_row)
            if resolved:
                universe = resolved

    frequency = BarFrequency.parse(bar_frequency or inherited_frequency or BarFrequency.DAILY)
    start, end = resolve_range_preset(range_preset)
    if strategy_id == "screening_rebalance":
        return {
            "error": "screening_rebalance_requires_history",
            "message": "选股调仓必须提供逐期点时选股快照；禁止用单次选股结果贯穿历史。",
            "required_interface": "SelectionSnapshotProvider.codes_as_of(date)",
        }
    if universe:
        from qmt_quant.core.universe import filter_universe_as_of

        universe = filter_universe_as_of(universe, start)
    n_label = f"{len(universe)} 只股票" if universe else "加载股票池"
    if job_id:
        report_job_progress(
            job_id,
            0.2,
            "加载行情数据…",
            step="load",
            detail=f"{start} ~ {end} · {n_label} · 策略 {strategy_id}",
        )
    signal_prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe,
        bar_frequency=frequency,
    )
    if signal_prices.empty:
        return {"error": "no_price_data"}

    signal_ohlcv = load_ohlcv_df(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or list(signal_prices.columns),
        bar_frequency=frequency,
    )
    # Execution always uses daily bars. Weekly signals become visible at the
    # actual final trading day's close and fill only into following daily rows.
    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or list(signal_prices.columns),
        bar_frequency=BarFrequency.DAILY,
    )
    ohlcv = load_ohlcv_df(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or list(signal_prices.columns),
        bar_frequency=BarFrequency.DAILY,
    )
    engine_name = engine or settings.validation_engine
    if frequency is BarFrequency.WEEKLY:
        engine_name = "custom"
    if strategy_id == "signal_replay":
        engine_name = "custom"
        if not universe or len(universe) != 1:
            n_cols = 0 if prices.empty else len(prices.columns)
            if n_cols != 1:
                return {
                    "error": "signal_replay_single_only",
                    "message": "信号回放仅支持单股回测，请指定一只股票。",
                }
            universe = list(prices.columns)
    validator = get_validation_engine(engine_name, match_price=match_price, slippage_bps=settings.slippage_bps)
    if job_id:
        report_job_progress(
            job_id,
            0.45,
            "按 A 股规则回测…",
            step="backtest",
            detail=(
                f"{len(prices.columns)} 只股票 · "
                f"{'MACD ' + str(fast_window) + '/' + str(slow_window) + '/' + str(signal_window) if strategy_id == 'macd_cross' else '均线 ' + str(short_window) + '/' + str(long_window)}"
                f" · 成交 {match_price}"
            ),
        )
    params: Dict[str, Any] = {
        "short_window": short_window,
        "long_window": long_window,
        "fast_window": fast_window,
        "slow_window": slow_window,
        "signal_window": signal_window,
        "screen_run_id": screen_run_id,
        "codes": universe or list(prices.columns),
        "signals": signals or [],
        "signal_prices": signal_prices,
        "signal_ohlcv": signal_ohlcv,
        "metadata": {"bar_frequency": frequency.value},
    }
    from qmt_quant.core.research.presets import FEE_PRESETS

    base_cost = CostModel.from_settings()
    commission_rate = FEE_PRESETS.get(fee_preset, FEE_PRESETS["default"])["commission_rate"]
    params["cost_model"] = CostModel(
        commission_rate=commission_rate,
        min_commission=base_cost.min_commission,
        stamp_duty_rate=base_cost.stamp_duty_rate,
        transfer_fee_rate=base_cost.transfer_fee_rate,
        slippage_bps=base_cost.slippage_bps,
    )
    params["portfolio"] = PortfolioSpec.for_universe(
        len(prices.columns), match_price=match_price
    )
    result = validator.run(strategy_id, prices, ohlcv=ohlcv, **params)

    engine_label = validation_engine_label(engine_name)
    if job_id:
        report_job_progress(job_id, 0.72, "汇总指标与结论…", step="compare")
    benchmark_curve = _benchmark_curve(benchmark, start, end)
    comparison = compare_with_research(result.total_return_pct, research_metrics)
    equity_series = {e["date"]: e["equity"] / 100 for e in result.equity_curve}
    quantstats = build_quantstats_summary(equity_series)

    resolved_codes = universe or list(prices.columns)
    trade_rows, trades_truncated = serialize_trades(result.trades, len(resolved_codes) or len(prices.columns))
    stock_returns: List[Dict[str, Any]] = []
    if len(resolved_codes) > 1:
        stock_returns = compute_per_stock_returns(
            strategy_id=strategy_id,
            prices=prices,
            ohlcv=ohlcv,
            codes=resolved_codes,
            match_price=match_price,
            slippage_bps=settings.slippage_bps,
            params=params,
            job_id=job_id,
        )

    payload: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "short_window": short_window,
        "long_window": long_window,
        "fast_window": fast_window,
        "slow_window": slow_window,
        "signal_window": signal_window,
        "match_price": match_price,
        "benchmark": benchmark,
        "benchmark_curve": benchmark_curve,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "trade_count": result.trade_count,
        "position_size_pct": params["portfolio"].position_size_pct,
        "verdict": comparison.get("verdict", result.verdict),
        "comparison": comparison,
        "equity_curve": result.equity_curve,
        "trades": trade_rows,
        "trades_truncated": trades_truncated,
        "quantstats": quantstats,
        "engine": engine_label,
        "engine_label": validation_engine_display_name(engine_name),
        "codes": resolved_codes,
        "bar_frequency": frequency.value,
        "execution_timing": (
            "周末实际最后交易日收盘确认信号，下一实际交易日开盘成交"
            if frequency is BarFrequency.WEEKLY
            else "日线收盘确认信号，下一实际交易日开盘成交"
        ),
    }
    if stock_returns:
        payload["stock_returns"] = stock_returns
    skipped = getattr(result, "skipped_signals", None) or []
    if skipped:
        payload["skipped_signals"] = skipped

    if job_id:
        report_job_progress(job_id, 0.9, "保存验证结果…", step="save")

    run_id = new_id()
    version, code_hash = strategy_identity(strategy_id)
    fingerprint = data_fingerprint(
        signal_prices, adjust=settings.bar_adjust_type, frequency=frequency.value
    )
    unified_metrics = compute_metrics(
        result.equity_curve, benchmark_curve=benchmark_curve, trades=trade_rows
    )
    payload["metrics"] = unified_metrics
    payload["diagnostics"] = build_diagnostics(
        result.equity_curve, stock_returns=stock_returns
    )
    payload["run_id"] = run_id
    artifact_paths = write_artifacts(
        run_id,
        manifest={
            "schema_version": 1,
            "run_id": run_id,
            "job_id": job_id,
            "run_kind": "validation",
            "engine": engine_label,
            "strategy_id": strategy_id,
            "strategy_version": version,
            "strategy_code_hash": code_hash,
            "settings": settings.to_dict(),
            "data_fingerprint": fingerprint,
            "universe": resolved_codes,
            "classification": "conclusion",
            "from_run_id": from_run_id,
        },
        detail=payload,
        equity=result.equity_curve,
        trades=trade_rows,
        positions=[],
    )
    with db_session() as conn:
        save_backtest_run(
            conn,
            engine=engine_label,
            strategy_id=strategy_id,
            title=f"validate {strategy_id} {fast_window}/{slow_window}/{signal_window}"
            if strategy_id == "macd_cross"
            else f"validate {strategy_id} {short_window}/{long_window}",
            params={
                "short_window": short_window,
                "long_window": long_window,
                "fast_window": fast_window,
                "slow_window": slow_window,
                "signal_window": signal_window,
                "match_price": match_price,
                "from_run_id": from_run_id,
                "screen_run_id": screen_run_id,
                "codes": universe,
                "bar_frequency": frequency.value,
            },
            metrics={
                "total_return_pct": result.total_return_pct,
                "verdict": payload["verdict"],
                "quantstats": quantstats,
                **unified_metrics,
            },
            result_path=artifact_paths["detail"],
            run_id=run_id,
            job_id=job_id,
            run_kind="validation",
            strategy_version=version,
            strategy_code_hash=code_hash,
            settings_snapshot=settings.to_dict(),
            data_fingerprint=fingerprint,
            universe=resolved_codes,
            artifact_dir=artifact_paths["artifact_dir"],
        )
    payload["result_path"] = artifact_paths["detail"]
    payload["artifact_paths"] = artifact_paths
    return payload


def _benchmark_curve(benchmark: str, start: str | None, end: str | None) -> list[dict]:
    if benchmark != "hs300":
        return []
    try:
        prices = load_price_matrix(codes=["000300.SH"], start_date=start, end_date=end)
        if prices.empty or "000300.SH" not in prices.columns:
            return []
        s = prices["000300.SH"].dropna()
        base = float(s.iloc[0])
        return [
            {"date": dt.strftime("%Y-%m-%d"), "equity": round(float(v) / base * 100, 2)}
            for dt, v in s.items()
        ]
    except Exception:
        return []
