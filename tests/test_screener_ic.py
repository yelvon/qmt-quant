"""IC analysis smoke tests."""

import numpy as np
import pandas as pd

from qmt_quant.core.screener.ic import _spearman, analyze_rolling_ic


def test_spearman_positive_correlation():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    ic = _spearman(x, y)
    assert ic > 0.99


def test_rolling_cross_sectional_ic_outputs_real_series_and_groups():
    dates = pd.date_range("2024-01-01", periods=12, freq="B")
    codes = list("ABCDE")
    base = np.arange(1, 6, dtype=float)
    prices = pd.DataFrame(
        [100 * (1 + base * 0.002) ** i for i in range(len(dates))],
        index=dates,
        columns=codes,
    )
    factor = pd.DataFrame([base] * 10, index=dates[:10], columns=codes)
    result = analyze_rolling_ic(prices, {"quality": factor}, horizons=[1, 2], quantiles=3)
    stats = result["factors"]["quality"]["horizons"]["1"]
    assert stats["dates"] == 10
    assert stats["ic_mean"] > 0.99
    assert len(stats["ic_series"]) == 10
    assert set(stats["quantile_returns"]) == {"1", "2", "3"}
    assert len(result["factors"]["quality"]["decay"]) == 2
