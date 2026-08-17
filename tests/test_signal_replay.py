"""Signal replay through AShareDailyBacktester."""

import pandas as pd

from qmt_quant.core.validation.backtester import AShareDailyBacktester


def test_signal_replay_next_open_two_buys_one_sell():
    dates = pd.date_range("2024-01-02", periods=10, freq="B")
    prices = pd.DataFrame({"600519.SH": [100 + i for i in range(10)]}, index=dates)
    rows = []
    for dt in dates:
        c = float(prices.loc[dt, "600519.SH"])
        rows.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "code": "600519.SH",
                "open": c,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
                "pre_close": c * 0.99,
            }
        )
    ohlcv = pd.DataFrame(rows)
    engine = AShareDailyBacktester(prices, ohlcv=ohlcv, match_price="next_open", enforce_limit=False)
    result = engine.run_signals(
        [
            {"date": "2024-01-03", "side": "B"},
            {"date": "2024-01-05", "side": "sell"},
            {"date": "2024-01-08", "side": "买入"},
            {"date": "2099-01-01", "side": "buy"},
        ]
    )
    sides = [(t.date, t.side) for t in result.trades]
    assert ("2024-01-04", "买入") in sides
    assert ("2024-01-08", "卖出") in sides
    assert ("2024-01-09", "买入") in sides
    assert result.trade_count == 3
    assert result.skipped_signals == [{"date": "2099-01-01", "reason": "no_bar"}]
