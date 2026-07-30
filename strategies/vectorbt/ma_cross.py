"""VectorBT dual moving average strategy helpers."""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from qmt_quant.core.research.presets import ma_param_combos


def generate_signals(prices: pd.DataFrame, short: int, long: int):
    try:
        import vectorbt as vbt

        fast = vbt.MA.run(prices, short, short_name="fast")
        slow = vbt.MA.run(prices, long, short_name="slow")
        entries = fast.ma_crossed_above(slow)
        exits = fast.ma_crossed_below(slow)
        return entries, exits
    except ImportError:
        fast = prices.rolling(short).mean()
        slow = prices.rolling(long).mean()
        signal = (fast > slow).astype(float)
        entries = (signal.diff() > 0)
        exits = (signal.diff() < 0)
        return entries, exits


def all_combos(short_preset: str, long_preset: str) -> List[Tuple[int, int]]:
    return ma_param_combos(short_preset, long_preset)
