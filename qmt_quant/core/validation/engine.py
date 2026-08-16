"""Validation engine protocol and factory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from qmt_quant.config import get_settings
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


class NautilusValidationEngine:
    """NautilusTrader backtest wrapper."""

    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs

    def run(
        self,
        strategy_id: str,
        prices: pd.DataFrame,
        *,
        ohlcv: pd.DataFrame | None = None,
        **params,
    ) -> ValidationResult:
        from qmt_quant.core.validation.nautilus_runner import run_nautilus_validation

        return run_nautilus_validation(
            strategy_id=strategy_id,
            prices=prices,
            short_window=int(params.get("short_window", 20)),
            long_window=int(params.get("long_window", 120)),
            codes=params.get("codes") or list(prices.columns),
        )


def get_validation_engine(name: str | None = None, **kwargs) -> ValidationEngine:
    engine_name = name or get_settings().validation_engine
    if engine_name == "nautilus":
        return NautilusValidationEngine(**kwargs)
    return CustomValidationEngine(**kwargs)


def validation_engine_label(name: str | None = None) -> str:
    """Internal engine id stored in DB / reports."""
    engine_name = name or get_settings().validation_engine
    return "nautilus" if engine_name == "nautilus" else "custom_validator"


def validation_engine_display_name(name: str | None = None) -> str:
    """User-facing engine name (never show raw ids in UI copy)."""
    engine_name = name or get_settings().validation_engine
    if engine_name == "nautilus":
        return "高保真引擎"
    return "A 股规则引擎"
