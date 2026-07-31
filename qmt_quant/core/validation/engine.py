"""Validation engine protocol and factory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from qmt_quant.core.validation.backtester import AShareDailyBacktester, ValidationResult


@runtime_checkable
class ValidationEngine(Protocol):
    def run(
        self,
        strategy_id: str,
        prices: pd.DataFrame,
        *,
        ohlcv: pd.DataFrame | None = None,
        **params,
    ) -> ValidationResult: ...


class CustomValidationEngine:
    """AShareDailyBacktester wrapper implementing ValidationEngine."""

    def __init__(self, **backtester_kwargs) -> None:
        self._kwargs = backtester_kwargs

    def run(
        self,
        strategy_id: str,
        prices: pd.DataFrame,
        *,
        ohlcv: pd.DataFrame | None = None,
        **params,
    ) -> ValidationResult:
        engine = AShareDailyBacktester(prices, ohlcv=ohlcv, **self._kwargs)
        if strategy_id == "ma_cross":
            return engine.run_ma_cross(
                int(params.get("short_window", 20)),
                int(params.get("long_window", 120)),
            )
        if strategy_id == "buy_hold":
            return engine.run_buy_hold()
        if strategy_id == "pe_momentum":
            return engine.run_pe_momentum(
                pe_threshold=float(params.get("pe_threshold", 30)),
                momentum_window=int(params.get("momentum_window", 20)),
            )
        if strategy_id == "screening_rebalance":
            return engine.run_screening_rebalance(
                params.get("screen_run_id"),
                rebalance_days=int(params.get("rebalance_days", 20)),
            )
        return engine.run_ma_cross(
            int(params.get("short_window", 20)),
            int(params.get("long_window", 120)),
        )


def get_validation_engine(name: str = "custom", **kwargs) -> ValidationEngine:
    if name == "nautilus":
        raise NotImplementedError("NautilusTrader engine planned for Phase 7")
    return CustomValidationEngine(**kwargs)
