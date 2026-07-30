"""VectorBT research runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import FEE_PRESETS, ma_param_combos
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import save_backtest_run


def run_research(
    *,
    strategy_id: str = "ma_cross",
    sector: str = "沪深A股",
    range_preset: str = "3y",
    short_preset: str = "preset_std",
    long_preset: str = "preset_std",
    fee_preset: str = "default",
    codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    run_migrations()
    settings = get_settings()
    start, end = resolve_range_preset(range_preset)
    universe = codes or resolve_universe(sector)
    if sector == "watchlist" or sector == "我的自选池":
        universe = resolve_universe("watchlist")

    prices = load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start,
        end_date=end,
        codes=universe[:50] if universe else None,
    )
    if prices.empty:
        return {"error": "no_price_data", "message": "请先同步日线数据"}

    fees = FEE_PRESETS.get(fee_preset, FEE_PRESETS["default"])["commission_rate"]

    if strategy_id == "ma_cross":
        result = _run_ma_cross_scan(prices, short_preset, long_preset, fees)
    elif strategy_id == "buy_hold":
        result = _run_buy_hold(prices, fees)
    else:
        result = _run_ma_cross_scan(prices, short_preset, long_preset, fees)

    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    result_path = reports_dir / f"research_{result['best']['label'].replace('/', '_')}.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with db_session() as conn:
        run_id = save_backtest_run(
            conn,
            engine="vectorbt",
            strategy_id=strategy_id,
            title=f"{strategy_id} {range_preset}",
            params={
                "sector": sector,
                "range_preset": range_preset,
                "short_preset": short_preset,
                "long_preset": long_preset,
                "fee_preset": fee_preset,
            },
            metrics=result["best"],
            result_path=str(result_path),
        )
    result["run_id"] = run_id
    result["result_path"] = str(result_path)
    return result


def _run_ma_cross_scan(
    prices: pd.DataFrame,
    short_preset: str,
    long_preset: str,
    fees: float,
) -> Dict[str, Any]:
    combos = ma_param_combos(short_preset, long_preset)
    rows: List[Dict[str, Any]] = []

    try:
        import vectorbt as vbt

        for short_w, long_w in combos:
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
