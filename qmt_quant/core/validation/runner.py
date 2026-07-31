"""Validation runner and comparison with research."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.catalog.export import load_ohlcv_df, load_price_matrix
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.report import build_quantstats_summary
from qmt_quant.core.validation.compare import compare_with_research
from qmt_quant.core.validation.engine import get_validation_engine
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import get_backtest_run, save_backtest_run


def run_validation(
    *,
    from_run_id: Optional[str] = None,
    strategy_id: str = "ma_cross",
    short_window: int = 20,
    long_window: int = 120,
    match_price: str = "next_open",
    benchmark: str = "hs300",
    range_preset: str = "3y",
    screen_run_id: Optional[str] = None,
    codes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    run_migrations()
    settings = get_settings()
    research_metrics = None
    if from_run_id:
        with db_session() as conn:
            research = get_backtest_run(conn, from_run_id)
        if research:
            research_metrics = research.get("metrics")
            params = research.get("params", {})
            best = research_metrics or {}
            label = best.get("label", "20/120")
            if strategy_id == "ma_cross" and "/" in str(label):
                parts = str(label).split("/")
                short_window = int(parts[0])
                long_window = int(parts[1])
            range_preset = params.get("range_preset", range_preset)
            strategy_id = research.get("strategy_id", strategy_id)
            screen_run_id = params.get("screen_run_id", screen_run_id)

    start, end = resolve_range_preset(range_preset)
    universe = codes
    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe,
    )
    if prices.empty:
        return {"error": "no_price_data"}

    ohlcv = load_ohlcv_df(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe or list(prices.columns),
    )
    engine = get_validation_engine(
        match_price=match_price,
        slippage_bps=settings.slippage_bps,
    )
    params: Dict[str, Any] = {
        "short_window": short_window,
        "long_window": long_window,
        "screen_run_id": screen_run_id,
    }
    result = engine.run(strategy_id, prices, ohlcv=ohlcv, **params)

    benchmark_curve = _benchmark_curve(benchmark, start, end)
    comparison = compare_with_research(result.total_return_pct, research_metrics)
    equity_series = {e["date"]: e["equity"] / 100 for e in result.equity_curve}
    quantstats = build_quantstats_summary(equity_series)

    payload: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "short_window": short_window,
        "long_window": long_window,
        "match_price": match_price,
        "benchmark": benchmark,
        "benchmark_curve": benchmark_curve,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "trade_count": result.trade_count,
        "verdict": comparison.get("verdict", result.verdict),
        "comparison": comparison,
        "equity_curve": result.equity_curve,
        "trades": [t.__dict__ for t in result.trades[:20]],
        "quantstats": quantstats,
        "engine": "custom_validator",
    }

    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    out = reports_dir / f"validate_{strategy_id}_{short_window}_{long_window}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with db_session() as conn:
        run_id = save_backtest_run(
            conn,
            engine="nautilus",
            strategy_id=strategy_id,
            title=f"validate {strategy_id} {short_window}/{long_window}",
            params={
                "short_window": short_window,
                "long_window": long_window,
                "match_price": match_price,
                "from_run_id": from_run_id,
                "screen_run_id": screen_run_id,
            },
            metrics={
                "total_return_pct": result.total_return_pct,
                "verdict": payload["verdict"],
                "quantstats": quantstats,
            },
            result_path=str(out),
        )
    payload["run_id"] = run_id
    payload["result_path"] = str(out)
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
