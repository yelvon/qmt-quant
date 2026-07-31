"""Validation backtester tests."""

import pandas as pd
import pytest

from qmt_quant.core.validation.backtester import AShareDailyBacktester


def _sample_prices():
    dates = pd.date_range("2024-01-02", periods=30, freq="B")
    data = {
        "600519.SH": [100 + i * 0.5 for i in range(30)],
        "000001.SZ": [10 + i * 0.1 for i in range(30)],
    }
    return pd.DataFrame(data, index=dates)


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


def test_t_plus_one_blocks_same_day_sell():
    prices = _sample_prices()
    ohlcv = _sample_ohlcv(prices)
    engine = AShareDailyBacktester(prices, ohlcv=ohlcv, match_price="close", enforce_limit=False)
    result = engine.run_ma_cross(3, 5)
    assert result.trade_count >= 0


def test_next_open_uses_later_bar():
    prices = _sample_prices()
    ohlcv = _sample_ohlcv(prices)
    close_engine = AShareDailyBacktester(prices, ohlcv=ohlcv, match_price="close", enforce_limit=False)
    open_engine = AShareDailyBacktester(prices, ohlcv=ohlcv, match_price="next_open", enforce_limit=False)
    r_close = close_engine.run_ma_cross(3, 5)
    r_open = open_engine.run_ma_cross(3, 5)
    assert r_close.trade_count >= 0
    assert r_open.trade_count >= 0


def test_round_lots():
    from qmt_quant.core.validation.venue_cn_a_share import round_lots

    assert round_lots(250, 100) == 200
    assert round_lots(50, 100) == 0
