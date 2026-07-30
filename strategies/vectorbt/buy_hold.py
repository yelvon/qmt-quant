"""Buy and hold benchmark."""

from __future__ import annotations

import pandas as pd


def total_return(prices: pd.DataFrame, fee: float = 0.0) -> float:
    rets = prices.pct_change().fillna(0).mean(axis=1)
    return float((1 + rets).prod() - 1 - fee)
