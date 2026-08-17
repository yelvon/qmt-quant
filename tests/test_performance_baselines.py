"""Opt-in representative performance baselines (run with ``-m performance``)."""

from time import perf_counter

import numpy as np
import pandas as pd
import pytest

from qmt_quant.core.data.frequency import aggregate_daily_to_weekly
from qmt_quant.core.backtest.kernels import numpy_ma_scan
from qmt_quant.core.screener.ic import analyze_rolling_ic

pytestmark = pytest.mark.performance


@pytest.fixture(scope="module")
def market() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2014-01-02", periods=2520, freq="B")
    returns = rng.normal(0.0002, 0.015, size=(len(dates), 300))
    return pd.DataFrame(
        10 * np.exp(np.cumsum(returns, axis=0)),
        index=dates,
        columns=[f"{i:06d}.SZ" for i in range(300)],
    )


def test_daily_300_stocks_10_years_single_parameter(market):
    started = perf_counter()
    result = numpy_ma_scan(market, [(20, 120)], 0.0003)
    assert result and perf_counter() - started < 30


def test_weekly_300_stocks_10_years(market):
    bars = market.stack().rename("close").reset_index()
    bars.columns = ["date", "code", "close"]
    bars["open"] = bars["high"] = bars["low"] = bars["close"]
    started = perf_counter()
    weekly = aggregate_daily_to_weekly(bars)
    assert len(weekly) > 0 and perf_counter() - started < 30


def test_rolling_ic_representative_panel(market):
    factor = market.pct_change(20).iloc[::5]
    started = perf_counter()
    result = analyze_rolling_ic(
        market, {"momentum": factor}, horizons=[5, 20], min_cross_section=30
    )
    assert result["ic"] and perf_counter() - started < 60


def test_typical_scan_parameter_grid(market):
    combos = [(s, long) for s in (5, 10, 20, 30) for long in (60, 120, 180, 250)]
    started = perf_counter()
    result = numpy_ma_scan(market, combos, 0.0003)
    assert len(result) == 16 and perf_counter() - started < 120
