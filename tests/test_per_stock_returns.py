"""Per-stock returns tests."""

import pandas as pd

from qmt_quant.core.validation.backtester import AShareDailyBacktester
from qmt_quant.core.validation.per_stock import compute_per_stock_returns


def _sample_prices():
    dates = pd.date_range("2024-01-02", periods=40, freq="B")
    up = [10 + i * 0.2 for i in range(40)]
    flat = [10.0] * 40
    return pd.DataFrame({"600519.SH": up, "000001.SZ": flat}, index=dates)


def _sample_ohlcv(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dt in prices.index:
        for code in prices.columns:
            c = float(prices.loc[dt, code])
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "code": code,
                    "open": c,
                    "high": c * 1.01,
                    "low": c * 0.99,
                    "close": c,
                    "pre_close": c * 0.99,
                }
            )
    return pd.DataFrame(rows)


def test_position_size_pct_affects_single_stock_return():
    prices = _sample_prices()[["600519.SH"]]
    ohlcv = _sample_ohlcv(prices)
    partial = AShareDailyBacktester(
        prices, ohlcv=ohlcv, match_price="close", enforce_limit=False, position_size_pct=0.1
    )
    full = AShareDailyBacktester(
        prices, ohlcv=ohlcv, match_price="close", enforce_limit=False, position_size_pct=1.0
    )
    r_partial = partial.run_buy_hold()
    r_full = full.run_buy_hold()
    assert r_full.total_return_pct >= r_partial.total_return_pct


def test_compute_per_stock_returns_sorted_and_skips_single():
    prices = _sample_prices()
    ohlcv = _sample_ohlcv(prices)
    rows = compute_per_stock_returns(
        strategy_id="buy_hold",
        prices=prices,
        ohlcv=ohlcv,
        codes=list(prices.columns),
        match_price="close",
        slippage_bps=0,
        params={},
    )
    assert len(rows) == 2
    assert rows[0]["total_return_pct"] >= rows[1]["total_return_pct"]
    assert rows[0]["code"] == "600519.SH"

    single = compute_per_stock_returns(
        strategy_id="buy_hold",
        prices=prices[["600519.SH"]],
        ohlcv=ohlcv,
        codes=["600519.SH"],
        match_price="close",
        slippage_bps=0,
        params={},
    )
    assert single == []
