"""Golden matching and portfolio-accounting invariants."""

import pandas as pd
import pytest

from qmt_quant.core.validation.backtester import AShareDailyBacktester
from qmt_quant.core.validation.venue_cn_a_share import (
    FeeConfig,
    daily_price_limit_ratio,
    match_buy,
    match_sell,
)


def test_pure_matcher_never_overspends_or_oversells():
    fees = FeeConfig()
    buy = match_buy(
        cash=10_005, budget=20_000, price=10, code="600000.SH", fees=fees
    )
    assert buy is not None
    assert buy.quantity % 100 == 0
    assert buy.cash_delta >= -10_005
    sell = match_sell(
        available=buy.quantity, quantity=buy.quantity + 100, price=11,
        code="600000.SH", fees=fees,
    )
    assert sell is not None
    assert sell.quantity == buy.quantity


def test_portfolio_ledger_invariants():
    dates = pd.date_range("2024-01-02", periods=6, freq="B")
    prices = pd.DataFrame({"600000.SH": [10, 11, 12, 11, 10, 9]}, index=dates)
    result = AShareDailyBacktester(
        prices,
        initial_cash=100_000,
        position_size_pct=1,
        enforce_limit=False,
        commission_rate=0,
        min_commission=0,
        transfer_fee_rate=0,
        stamp_tax_rate=0,
    ).run_ma_cross(1, 2)
    for row in result.equity_curve:
        assert row["cash"] >= -1e-8
        assert row["equity_value"] == pytest.approx(
            row["cash"] + row["market_value"], abs=1e-7
        )
    assert all(trade.quantity % 100 == 0 for trade in result.trades)


def test_future_prices_do_not_change_past_fills():
    dates = pd.date_range("2024-01-02", periods=8, freq="B")
    base = pd.DataFrame({"600000.SH": [10, 11, 12, 13, 14, 13, 12, 11]}, index=dates)
    changed = base.copy()
    changed.iloc[5:, 0] = [1000, 1, 500]
    kwargs = dict(
        initial_cash=100_000, enforce_limit=False, commission_rate=0,
        min_commission=0, transfer_fee_rate=0, stamp_tax_rate=0,
    )
    left = AShareDailyBacktester(base, **kwargs).run_ma_cross(1, 2)
    right = AShareDailyBacktester(changed, **kwargs).run_ma_cross(1, 2)
    cutoff = dates[5].strftime("%Y-%m-%d")
    left_past = [t for t in left.trades if t.date < cutoff]
    right_past = [t for t in right.trades if t.date < cutoff]
    assert left_past == right_past


@pytest.mark.parametrize(
    ("code", "day", "is_st", "expected"),
    [
        ("600000.SH", "2024-01-01", False, 0.10),
        ("300001.SZ", "2020-08-21", False, 0.10),
        ("300001.SZ", "2020-08-24", False, 0.20),
        ("688001.SH", "2024-01-01", False, 0.20),
        ("830001.BJ", "2024-01-01", False, 0.30),
        ("600000.SH", "2024-01-01", True, 0.05),
    ],
)
def test_a_share_board_and_st_price_limits(code, day, is_st, expected):
    assert daily_price_limit_ratio(code, day, is_st=is_st) == expected
