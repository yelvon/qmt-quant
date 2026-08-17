"""MACD golden/death cross strategy tests."""

import pandas as pd

from qmt_quant.core.backtest.strategy import STRATEGIES, StrategyContext, macd_lines
from qmt_quant.core.validation.backtester import AShareDailyBacktester


def _rising_then_falling() -> pd.DataFrame:
    index = pd.date_range("2020-01-02", periods=80, freq="B")
    up = [10 + i * 0.4 for i in range(50)]
    down = [up[-1] - i * 0.6 for i in range(1, 31)]
    return pd.DataFrame({"000001.SZ": up + down}, index=index)


def test_macd_strategy_is_registered():
    assert "macd_cross" in STRATEGIES.ids()


def test_macd_holds_after_golden_cross_and_exits_after_death_cross():
    prices = _rising_then_falling()
    signal = STRATEGIES.get("macd_cross").signal(StrategyContext(prices=prices), {})
    series = signal["000001.SZ"]
    warmup = 30
    assert series.iloc[warmup:50].mean() > 0.7
    assert series.iloc[-8:].mean() < 0.5


def test_macd_lines_fast_reacts_before_slow():
    prices = _rising_then_falling()
    dif, dea = macd_lines(prices, fast_window=12, slow_window=26, signal_window=9)
    assert float(dif.iloc[40, 0]) > 0
    assert not bool(dif.isna().all().iloc[0])
    assert not bool(dea.isna().all().iloc[0])


def test_macd_backtest_produces_trades():
    prices = _rising_then_falling()
    result = AShareDailyBacktester(
        prices, match_price="close", enforce_limit=False, position_size_pct=1.0
    ).run_strategy("macd_cross", {"fast_window": 8, "slow_window": 21, "signal_window": 7})
    assert result.trade_count >= 2
    sides = [t.side for t in result.trades]
    assert "买入" in sides
    assert "卖出" in sides


def test_high_price_10pct_cannot_buy_one_lot():
    index = pd.date_range("2020-01-02", periods=6, freq="B")
    prices = pd.DataFrame({"600519.SH": [1800.0] * 6}, index=index)
    result = AShareDailyBacktester(
        prices,
        match_price="close",
        enforce_limit=False,
        position_size_pct=0.1,
        initial_cash=1_000_000,
    ).run_buy_hold()
    assert result.trade_count == 0
    assert any(row["reason"] == "insufficient_cash_for_lot" for row in result.skipped_signals)


def test_single_name_universe_can_buy_moutai_lot():
    from qmt_quant.core.backtest.strategy import PortfolioSpec

    index = pd.date_range("2020-01-02", periods=6, freq="B")
    prices = pd.DataFrame({"600519.SH": [1800.0] * 6}, index=index)
    portfolio = PortfolioSpec.for_universe(1, initial_cash=1_000_000, match_price="close")
    assert portfolio.position_size_pct == 1.0
    result = AShareDailyBacktester(
        prices, enforce_limit=False, portfolio=portfolio
    ).run_buy_hold()
    assert result.trade_count >= 1
    assert result.trades[0].quantity >= 100
    assert result.trades[0].quantity % 100 == 0


def test_macd_candidates_require_fast_slower_than_slow():
    rows = list(STRATEGIES.get("macd_cross").candidate_params({}))
    assert rows
    assert all(row["fast_window"] < row["slow_window"] for row in rows)
    assert all({"fast_window", "slow_window", "signal_window"} <= set(row) for row in rows)
