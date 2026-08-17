import pandas as pd

from qmt_quant.core.data.frequency import (
    BarFrequency,
    aggregate_daily_to_weekly,
    apply_bar_frequency,
)
from qmt_quant.core.validation.backtester import AShareDailyBacktester


def test_manual_weekly_aggregation_uses_actual_trading_dates():
    daily = pd.DataFrame(
        [
            # Holiday-shortened week ends on Thursday.
            {
                "date": "2024-04-01",
                "code": "000001.SZ",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "amount": 1000,
                "pre_close": 9.5,
                "adjust_type": "front",
            },
            {
                "date": "2024-04-03",
                "code": "000001.SZ",
                "open": 11,
                "high": 13,
                "low": 10,
                "close": 12,
                "volume": 200,
                "amount": 2200,
                "pre_close": 11,
                "adjust_type": "front",
            },
            {
                "date": "2024-04-04",
                "code": "000001.SZ",
                "open": 12,
                "high": 14,
                "low": 8,
                "close": 13,
                "volume": 300,
                "amount": 3600,
                "pre_close": 12,
                "adjust_type": "front",
            },
            {
                "date": "2024-04-08",
                "code": "000001.SZ",
                "open": 15,
                "high": 16,
                "low": 14,
                "close": 15.5,
                "volume": 400,
                "amount": 6000,
                "pre_close": 13,
                "adjust_type": "front",
            },
        ]
    )

    weekly = aggregate_daily_to_weekly(daily)

    assert weekly["date"].dt.strftime("%Y-%m-%d").tolist() == ["2024-04-04", "2024-04-08"]
    first = weekly.iloc[0]
    assert first["open"] == 10
    assert first["high"] == 14
    assert first["low"] == 8
    assert first["close"] == 13
    assert first["volume"] == 600
    assert first["amount"] == 6800
    assert first["pre_close"] == 9.5
    assert first["adjust_type"] == "front"
    assert apply_bar_frequency(daily, BarFrequency.DAILY)["date"].iloc[0] == "2024-04-01"


def test_weekly_close_signal_executes_next_actual_daily_open():
    dates = pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-03", "2024-04-04", "2024-04-08"])
    prices = pd.DataFrame({"000001.SZ": [10, 10, 10, 10, 30]}, index=dates)
    daily_ohlcv = pd.DataFrame(
        [
            {
                "date": dt,
                "code": "000001.SZ",
                "open": 20 if dt == pd.Timestamp("2024-04-08") else 10,
                "high": 30,
                "low": 9,
                "close": float(prices.loc[dt, "000001.SZ"]),
                "pre_close": 10,
                "volume": 100,
            }
            for dt in dates
        ]
    )
    engine = AShareDailyBacktester(
        prices,
        ohlcv=daily_ohlcv,
        match_price="next_open",
        enforce_limit=False,
        initial_cash=100_000,
        position_size_pct=0.9,
        slippage_bps=0,
    )
    weekly_signal = pd.DataFrame(
        {"000001.SZ": [1.0]},
        index=pd.to_datetime(["2024-04-04"]),
    )

    expanded = engine._expand_signal_to_execution_calendar(weekly_signal)
    result = engine._run_signal_loop(expanded, include_first_bar=True)

    assert result.trade_count == 1
    assert result.trades[0].date == "2024-04-08"
    assert result.trades[0].price == 20
