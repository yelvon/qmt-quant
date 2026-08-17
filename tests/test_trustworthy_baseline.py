"""Golden rules for bias-free research and execution."""

import pandas as pd

from qmt_quant.core.research.runner import (
    _equity_from_result,
    _run_buy_hold,
    _run_ma_cross_scan,
)
from qmt_quant.core.validation.backtester import AShareDailyBacktester


def test_research_equity_is_strategy_equity_not_stock_equal_weight():
    dates = pd.date_range("2024-01-01", periods=6, freq="B")
    prices = pd.DataFrame(
        {"AAA.SH": [10, 11, 12, 13, 14, 15], "BBB.SH": [10, 9, 8, 7, 6, 5]},
        index=dates,
    )
    result = _run_ma_cross_scan(prices, "preset_fast", "preset_fast", 0)
    equity = _equity_from_result(result, prices)
    equal_weight = (1 + prices.pct_change().fillna(0).mean(axis=1)).cumprod()
    assert list(equity.values()) != list(equal_weight.astype(float))


def test_buy_hold_emits_its_own_equity_curve():
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    prices = pd.DataFrame({"AAA.SH": [10, 11, 12]}, index=dates)
    result = _run_buy_hold(prices, 0.001)
    assert result["equity_curve"]
    assert result["equity_curve"][-1]["equity"] > 100


def test_zero_volume_bar_blocks_fill_and_records_reason():
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    prices = pd.DataFrame({"AAA.SH": [10, 11, 12]}, index=dates)
    ohlcv = pd.DataFrame(
        [
            {
                "date": dt.strftime("%Y-%m-%d"),
                "code": "AAA.SH",
                "open": float(prices.loc[dt, "AAA.SH"]),
                "high": 12.0,
                "low": 9.0,
                "close": float(prices.loc[dt, "AAA.SH"]),
                "pre_close": 10.0,
                "volume": 0 if i == 1 else 100,
            }
            for i, dt in enumerate(dates)
        ]
    )
    engine = AShareDailyBacktester(
        prices, ohlcv=ohlcv, match_price="next_open", enforce_limit=False
    )
    result = engine.run_buy_hold()
    assert result.trade_count == 0
    assert result.skipped_signals[0]["reason"] == "suspended_volume_zero"


def test_static_screening_history_is_rejected():
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    prices = pd.DataFrame({"AAA.SH": [10, 11, 12]}, index=dates)
    result = AShareDailyBacktester(prices).run_screening_rebalance("run-once")
    assert result.trade_count == 0
    assert "point_in_time" in result.skipped_signals[0]["reason"]
