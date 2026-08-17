"""Shared strategy plugin contract tests."""

import pandas as pd

from qmt_quant.core.backtest.strategy import (
    STRATEGIES,
    SignalStrategyPlugin,
    StrategyContext,
    StrategyRegistry,
)
from qmt_quant.core.validation.backtester import AShareDailyBacktester, BacktestResult
from qmt_quant.core.validation.engine import CustomValidationEngine


def _prices() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=40, freq="B")
    return pd.DataFrame({"000001.SZ": [10 + i * 0.1 for i in range(40)]}, index=index)


def test_builtin_strategies_are_registered():
    assert {"ma_cross", "buy_hold", "pe_momentum", "screening_rebalance"} <= set(
        STRATEGIES.ids()
    )


def test_new_plugin_requires_no_engine_branch():
    registry = StrategyRegistry()
    plugin = SignalStrategyPlugin(
        "always_in",
        lambda context, params: pd.DataFrame(
            1.0, index=context.prices.index, columns=context.prices.columns
        ),
        include_first_bar=True,
    )
    registry.register(plugin)
    assert registry.get("always_in") is plugin


def test_custom_engine_dispatches_through_registry():
    plugin = SignalStrategyPlugin(
        "test_always_in",
        lambda context, params: pd.DataFrame(
            1.0, index=context.prices.index, columns=context.prices.columns
        ),
        include_first_bar=True,
    )
    STRATEGIES.register(plugin)
    result = CustomValidationEngine(
        match_price="close", enforce_limit=False
    ).run("test_always_in", _prices())
    assert isinstance(result, BacktestResult)
    assert result.trade_count == 1


def test_legacy_methods_return_unified_result():
    result = AShareDailyBacktester(
        _prices(), match_price="close", enforce_limit=False
    ).run_ma_cross(3, 5)
    assert isinstance(result, BacktestResult)
