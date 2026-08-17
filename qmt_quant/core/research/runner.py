"""VectorBT research runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.backtest.strategy import (
    STRATEGIES,
    CostModel,
    PortfolioSpec,
    StrategyContext,
)
from qmt_quant.core.backtest.experiments import (
    build_diagnostics,
    compute_metrics,
    data_fingerprint,
    strategy_identity,
    write_artifacts,
)
from qmt_quant.core.backtest.kernels import numpy_ma_scan
from qmt_quant.core.catalog.export import load_ohlcv_df, load_price_matrix
from qmt_quant.core.data.frequency import BarFrequency
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import FEE_PRESETS, ma_param_combos
from qmt_quant.core.research.report import build_quantstats_summary
from qmt_quant.core.research.universe import resolve_research_universe_meta
from qmt_quant.core.screener.bridge import load_codes_by_run_id
from qmt_quant.core.universe import mask_prices_by_lifecycle
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import new_id, save_backtest_run


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
    sample: str = "all",
    universe_n: Optional[int] = None,
    replay_top_n: int = 5,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    settings = get_settings()
    frequency = BarFrequency.parse(bar_frequency)
    if strategy_id == "signal_replay":
        return {
            "error": "signal_replay_use_backtest",
            "message": "信号回放请使用单股回测，不走参数扫描。",
        }
    if job_id:
        report_job_progress(
            job_id,
            0.08,
            "加载行情数据…",
            step="load",
            detail=f"策略 {strategy_id} · 区间 {range_preset}",
        )
    start, end = resolve_range_preset(range_preset)
    load_codes, uni_meta = resolve_research_universe_meta(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
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
        codes=load_codes if load_codes else None,
        bar_frequency=frequency,
    )
    prices = mask_prices_by_lifecycle(prices)
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

    preset_fee = FEE_PRESETS.get(fee_preset, FEE_PRESETS["default"])["commission_rate"]
    base_cost = CostModel.from_settings()
    cost_model = CostModel(
        commission_rate=preset_fee,
        min_commission=base_cost.min_commission,
        stamp_duty_rate=base_cost.stamp_duty_rate,
        transfer_fee_rate=base_cost.transfer_fee_rate,
        slippage_bps=base_cost.slippage_bps,
    )
    portfolio = PortfolioSpec.from_settings()
    runner = _RESEARCH_RUNNERS.get(strategy_id)
    if runner is None:
        STRATEGIES.get(strategy_id)
        runner = _run_registered_strategy
    selection_provider = None
    if strategy_id == "screening_rebalance":
        from qmt_quant.core.screener.snapshots import RuleSelectionSnapshotProvider

        selection_provider = RuleSelectionSnapshotProvider(sector=sector)
    result = runner(
        prices,
        preset_fee,
        {
            "strategy_id": strategy_id,
            "short_preset": short_preset,
            "long_preset": long_preset,
            "screen_run_id": screen_run_id,
            "job_id": job_id,
            "bar_frequency": frequency.value,
            "selection_snapshot_provider": selection_provider,
        },
    )
    ohlcv = load_ohlcv_df(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=list(prices.columns),
        bar_frequency=frequency,
    )
    execution_prices = prices
    execution_ohlcv = ohlcv
    if frequency is BarFrequency.WEEKLY:
        execution_prices = load_price_matrix(
            adjust_type=settings.bar_adjust_type,
            start_date=start,
            end_date=end,
            codes=list(prices.columns),
            bar_frequency=BarFrequency.DAILY,
        )
        execution_ohlcv = load_ohlcv_df(
            adjust_type=settings.bar_adjust_type,
            start_date=start,
            end_date=end,
            codes=list(prices.columns),
            bar_frequency=BarFrequency.DAILY,
        )
    _rerank_with_a_share_kernel(
        result,
        strategy_id,
        prices,
        ohlcv,
        cost_model,
        portfolio,
        execution_prices=execution_prices,
        execution_ohlcv=execution_ohlcv,
        top_n=replay_top_n,
        metadata={"selection_snapshot_provider": selection_provider}
        if selection_provider is not None
        else None,
    )

    equity_map = _equity_from_result(result, prices)
    result["quantstats"] = build_quantstats_summary(equity_map)
    result["best"]["quantstats"] = result["quantstats"]
    used_codes = list(prices.columns)
    result["universe_codes"] = used_codes

    if job_id:
        report_job_progress(job_id, 0.88, "保存回测结果…", step="save")

    run_id = new_id()
    version, code_hash = strategy_identity(strategy_id)
    fingerprint = data_fingerprint(
        prices, adjust=settings.bar_adjust_type, frequency=frequency.value
    )
    unified_metrics = compute_metrics(result.get("equity_curve") or [])
    result["metrics"] = unified_metrics
    result["diagnostics"] = build_diagnostics(result.get("equity_curve") or [])
    result["run_id"] = run_id
    artifact_paths = write_artifacts(
        run_id,
        manifest={
            "schema_version": 1,
            "run_id": run_id,
            "job_id": job_id,
            "run_kind": "scan",
            "engine": "vectorbt+a_share_daily",
            "strategy_id": strategy_id,
            "strategy_version": version,
            "strategy_code_hash": code_hash,
            "settings": settings.to_dict(),
            "data_fingerprint": fingerprint,
            "universe": used_codes,
            "classification": "candidate",
        },
        detail=result,
        equity=result.get("equity_curve"),
    )
    with db_session() as conn:
        save_backtest_run(
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
                "sample": uni_meta.get("sample") or sample,
                "universe_n": uni_meta.get("universe_n"),
                "replay_top_n": replay_top_n,
                "bar_frequency": frequency.value,
            },
            metrics={**result["best"], **unified_metrics},
            result_path=artifact_paths["detail"],
            run_id=run_id,
            job_id=job_id,
            run_kind="scan",
            strategy_version=version,
            strategy_code_hash=code_hash,
            settings_snapshot=settings.to_dict(),
            data_fingerprint=fingerprint,
            universe=used_codes,
            artifact_dir=artifact_paths["artifact_dir"],
        )
    result["result_path"] = artifact_paths["detail"]
    result["artifact_paths"] = artifact_paths
    result["universe_used"] = len(used_codes)
    if uni_meta.get("sample_fallback"):
        result["sample_fallback"] = uni_meta["sample_fallback"]
    result["sample"] = uni_meta.get("sample") or sample
    result["bar_frequency"] = frequency.value
    return result


def _equity_from_result(result: Dict[str, Any], prices: pd.DataFrame) -> Dict[str, float]:
    if result.get("equity_curve"):
        return {e["date"]: e["equity"] / 100 for e in result["equity_curve"]}
    raise ValueError("research strategy did not produce a genuine strategy equity curve")


def _equity_curve(returns: pd.Series) -> List[Dict[str, Any]]:
    equity = (1 + returns.fillna(0)).cumprod()
    return [
        {"date": dt.strftime("%Y-%m-%d"), "equity": round(float(value) * 100, 8)}
        for dt, value in equity.items()
    ]


def _signal_returns(prices: pd.DataFrame, signal: pd.DataFrame, fees: float) -> pd.Series:
    returns = prices.pct_change().fillna(0)
    held = signal.shift(1).fillna(0)
    strategy_returns = (held * returns).mean(axis=1)
    turnover = held.diff().abs().fillna(held.abs()).mean(axis=1)
    return strategy_returns - turnover * fees


def _run_ma_cross_scan(
    prices: pd.DataFrame,
    short_preset: str,
    long_preset: str,
    fees: float,
    job_id: Optional[str] = None,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
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
                freq="1W" if BarFrequency.parse(bar_frequency) is BarFrequency.WEEKLY else "1D",
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
    fast = prices.rolling(int(best.get("short", 1))).mean()
    slow = prices.rolling(int(best.get("long", 1))).mean()
    equity_curve = _equity_curve(_signal_returns(prices, (fast > slow).astype(float), fees))
    return {
        "strategy": "ma_cross",
        "combos": rows,
        "best": best,
        "engine": "vectorbt",
        "equity_curve": equity_curve,
    }


def _numpy_ma_scan(
    prices: pd.DataFrame,
    combos: List[Tuple[int, int]],
    fees: float,
) -> List[Dict[str, Any]]:
    return numpy_ma_scan(prices, combos, fees, _signal_returns)


def _run_buy_hold(prices: pd.DataFrame, fees: float) -> Dict[str, Any]:
    rets = prices.pct_change().fillna(0).mean(axis=1)
    if len(rets):
        rets.iloc[0] -= fees
    total = float((1 + rets).prod() - 1)
    best = {"label": "buy_hold", "total_return_pct": round(total * 100, 2)}
    return {
        "strategy": "buy_hold",
        "combos": [best],
        "best": best,
        "engine": "vectorbt",
        "equity_curve": _equity_curve(rets),
    }


def _run_pe_momentum(prices: pd.DataFrame, fees: float) -> Dict[str, Any]:
    from qmt_quant.core.research.factors import load_pe_matrix

    with db_session() as conn:
        pe_mat = load_pe_matrix(conn, prices.index, list(prices.columns))
    mom = prices.pct_change(20)
    signal = ((pe_mat <= 30) & (mom > 0)).astype(float)
    rets = prices.pct_change().fillna(0)
    strat_ret = _signal_returns(prices, signal, fees)
    total = float((1 + strat_ret).prod() - 1)
    best = {"label": "pe_momentum", "total_return_pct": round(total * 100, 2)}
    return {
        "strategy": "pe_momentum",
        "combos": [best],
        "best": best,
        "engine": "vectorbt",
        "equity_curve": _equity_curve(strat_ret),
    }


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


def _run_registered_strategy(
    prices: pd.DataFrame,
    fees: float,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    plugin = STRATEGIES.get(str(options["strategy_id"]))
    params = {}
    signal = plugin.signal(
        StrategyContext(
            prices=prices,
            cost_model=CostModel.from_settings(),
            portfolio=PortfolioSpec.from_settings(),
            metadata={"bar_frequency": options.get("bar_frequency", BarFrequency.DAILY)},
        ),
        params,
    )
    returns = _signal_returns(prices, signal, fees)
    total = float((1 + returns).prod() - 1)
    best = {"label": plugin.strategy_id, "total_return_pct": round(total * 100, 2)}
    return {
        "strategy": plugin.strategy_id,
        "combos": [best],
        "best": best,
        "engine": "vectorbt",
        "equity_curve": _equity_curve(returns),
    }


def _ma_runner(prices: pd.DataFrame, fees: float, options: Dict[str, Any]) -> Dict[str, Any]:
    return _run_ma_cross_scan(
        prices,
        str(options["short_preset"]),
        str(options["long_preset"]),
        fees,
        job_id=options.get("job_id"),
        bar_frequency=options.get("bar_frequency", BarFrequency.DAILY),
    )


def _buy_hold_runner(
    prices: pd.DataFrame, fees: float, options: Dict[str, Any]
) -> Dict[str, Any]:
    return _run_buy_hold(prices, fees)


def _pe_runner(prices: pd.DataFrame, fees: float, options: Dict[str, Any]) -> Dict[str, Any]:
    return _run_pe_momentum(prices, fees)


def _screening_runner(
    prices: pd.DataFrame, fees: float, options: Dict[str, Any]
) -> Dict[str, Any]:
    provider = options.get("selection_snapshot_provider")
    plugin = STRATEGIES.get("screening_rebalance")
    audit: List[Dict[str, Any]] = []
    signal = plugin.signal(
        StrategyContext(
            prices=prices,
            cost_model=CostModel.from_settings(),
            portfolio=PortfolioSpec.from_settings(),
            metadata={
                "selection_snapshot_provider": provider,
                "selection_audit": audit,
            },
        ),
        {"rebalance_days": 20},
    )
    returns = _signal_returns(prices, signal, fees)
    total = float((1 + returns).prod() - 1)
    best = {"label": "screening_rebalance", "total_return_pct": round(total * 100, 2)}
    return {
        "strategy": "screening_rebalance",
        "combos": [best],
        "best": best,
        "engine": "vectorbt",
        "equity_curve": _equity_curve(returns),
        "selection_audit": audit,
    }


_RESEARCH_RUNNERS = {
    "ma_cross": _ma_runner,
    "buy_hold": _buy_hold_runner,
    "pe_momentum": _pe_runner,
    "screening_rebalance": _screening_runner,
}


def _candidate_params(strategy_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if strategy_id == "ma_cross":
        return {
            "short_window": int(row.get("short", 20)),
            "long_window": int(row.get("long", 120)),
        }
    return {}


def _rerank_with_a_share_kernel(
    result: Dict[str, Any],
    strategy_id: str,
    prices: pd.DataFrame,
    ohlcv: pd.DataFrame,
    cost_model: CostModel,
    portfolio: PortfolioSpec,
    *,
    top_n: int,
    execution_prices: pd.DataFrame | None = None,
    execution_ohlcv: pd.DataFrame | None = None,
    metadata: Dict[str, Any] | None = None,
) -> None:
    """Replay fast-scan finalists with the same A-share execution kernel."""
    from qmt_quant.core.validation.backtester import AShareDailyBacktester

    candidates = list(result.get("combos") or [])[: max(1, int(top_n))]
    replayed: List[Dict[str, Any]] = []
    best_result = None
    for candidate in candidates:
        params = _candidate_params(strategy_id, candidate)
        replay = AShareDailyBacktester(
            execution_prices if execution_prices is not None else prices,
            ohlcv=execution_ohlcv if execution_ohlcv is not None else ohlcv,
            signal_prices=prices,
            signal_ohlcv=ohlcv,
            cost_model=cost_model,
            portfolio=portfolio,
        ).run_strategy(strategy_id, params, metadata=metadata)
        row = {
            **candidate,
            "scan_total_return_pct": candidate.get("total_return_pct", 0),
            "total_return_pct": replay.total_return_pct,
            "max_drawdown_pct": replay.max_drawdown_pct,
            "trade_count": replay.trade_count,
            "replayed_by": "a_share_daily",
        }
        replayed.append(row)
        if best_result is None or replay.total_return_pct > best_result.total_return_pct:
            best_result = replay
    if not replayed:
        return
    replayed.sort(key=lambda row: row["total_return_pct"], reverse=True)
    result["scan_candidates"] = result.get("combos") or []
    result["combos"] = replayed
    result["best"] = replayed[0]
    result["ranking_engine"] = "a_share_daily"
    if best_result is not None:
        result["equity_curve"] = best_result.equity_curve
