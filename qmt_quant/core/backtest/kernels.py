"""Dependency-light, deterministic research calculation kernels."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence, Tuple

import pandas as pd


def signal_returns(prices: pd.DataFrame, signal: pd.DataFrame, fees: float) -> pd.Series:
    returns = prices.pct_change().fillna(0)
    held = signal.shift(1).fillna(0)
    strategy_returns = (held * returns).mean(axis=1)
    turnover = held.diff().abs().fillna(held.abs()).mean(axis=1)
    return strategy_returns - turnover * fees


def numpy_ma_scan(
    prices: pd.DataFrame,
    combos: Sequence[Tuple[int, int]],
    fees: float,
    signal_return_fn: Callable[[pd.DataFrame, pd.DataFrame, float], pd.Series] = signal_returns,
) -> List[Dict[str, Any]]:
    """Pure moving-average parameter scan over an in-memory price matrix."""
    rows: List[Dict[str, Any]] = []
    for short_w, long_w in combos:
        fast = prices.rolling(short_w).mean()
        slow = prices.rolling(long_w).mean()
        signal = (fast > slow).astype(float)
        strat_ret = signal_return_fn(prices, signal, fees)
        total = float((1 + strat_ret).prod() - 1)
        rows.append(
            {
                "short": short_w,
                "long": long_w,
                "label": f"{short_w}/{long_w}",
                "total_return_pct": round(total * 100, 2),
            }
        )
    return rows
