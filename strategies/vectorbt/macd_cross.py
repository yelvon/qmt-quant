"""VectorBT MACD golden/death cross helpers."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from qmt_quant.core.backtest.strategy import STRATEGIES, macd_lines


def generate_signals(
    prices: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
):
    dif, dea = macd_lines(
        prices, fast_window=fast, slow_window=slow, signal_window=signal
    )
    held = (dif > dea).astype(float)
    entries = held.diff() > 0
    exits = held.diff() < 0
    return entries, exits


def all_combos(params: dict | None = None) -> Iterable[dict]:
    return STRATEGIES.get("macd_cross").candidate_params(params or {})
