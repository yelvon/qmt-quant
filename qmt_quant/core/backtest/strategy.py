"""Shared strategy plugins and backtest configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Protocol

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.core.validation.venue_cn_a_share import FeeConfig


@dataclass(frozen=True)
class CostModel:
    commission_rate: float
    min_commission: float
    stamp_duty_rate: float
    transfer_fee_rate: float
    slippage_bps: float

    @classmethod
    def from_settings(cls) -> "CostModel":
        settings = get_settings()
        return cls(
            commission_rate=settings.commission_rate,
            min_commission=settings.min_commission,
            stamp_duty_rate=settings.stamp_tax_rate,
            transfer_fee_rate=settings.transfer_fee_rate,
            slippage_bps=settings.slippage_bps,
        )

    def fee_config(self) -> FeeConfig:
        return FeeConfig(
            commission_rate=self.commission_rate,
            min_commission=self.min_commission,
            stamp_duty_rate=self.stamp_duty_rate,
            transfer_fee_rate=self.transfer_fee_rate,
        )


@dataclass(frozen=True)
class PortfolioSpec:
    initial_cash: float
    position_size_pct: float = 0.1
    match_price: str = "next_open"
    enforce_limit: bool = True

    @classmethod
    def from_settings(cls, **overrides: Any) -> "PortfolioSpec":
        settings = get_settings()
        values = {
            "initial_cash": settings.initial_cash,
            "position_size_pct": 0.1,
            "match_price": "next_open",
            "enforce_limit": True,
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)


@dataclass
class StrategyContext:
    prices: pd.DataFrame
    ohlcv: pd.DataFrame | None = None
    cost_model: CostModel = field(default_factory=CostModel.from_settings)
    portfolio: PortfolioSpec = field(default_factory=PortfolioSpec.from_settings)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    equity_curve: list[Dict[str, float]] = field(default_factory=list)
    trades: list[Any] = field(default_factory=list)
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    verdict: str = "可以采用"
    trade_count: int = 0
    skipped_signals: list[Dict[str, str]] = field(default_factory=list)
    selection_audit: list[Dict[str, Any]] = field(default_factory=list)


class StrategyPlugin(Protocol):
    strategy_id: str

    def signal(self, context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame: ...

    def candidate_params(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]: ...


class SignalStrategyPlugin:
    def __init__(
        self,
        strategy_id: str,
        signal_factory: Callable[[StrategyContext, Dict[str, Any]], pd.DataFrame],
        candidate_factory: Callable[[Dict[str, Any]], Iterable[Dict[str, Any]]] | None = None,
        *,
        hold_only: bool = False,
        include_first_bar: bool = False,
    ) -> None:
        self.strategy_id = strategy_id
        self._signal_factory = signal_factory
        self._candidate_factory = candidate_factory or (lambda params: [dict(params)])
        self.hold_only = hold_only
        self.include_first_bar = include_first_bar

    def signal(self, context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame:
        return self._signal_factory(context, params)

    def candidate_params(self, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        return self._candidate_factory(params)


class StrategyRegistry:
    def __init__(self) -> None:
        self._plugins: Dict[str, StrategyPlugin] = {}

    def register(self, plugin: StrategyPlugin) -> StrategyPlugin:
        if plugin.strategy_id in self._plugins:
            raise ValueError(f"strategy already registered: {plugin.strategy_id}")
        self._plugins[plugin.strategy_id] = plugin
        return plugin

    def get(self, strategy_id: str) -> StrategyPlugin:
        try:
            return self._plugins[strategy_id]
        except KeyError as exc:
            raise ValueError(f"unknown strategy: {strategy_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(self._plugins)


STRATEGIES = StrategyRegistry()


def register_strategy(plugin: StrategyPlugin) -> StrategyPlugin:
    return STRATEGIES.register(plugin)


def _ma_signal(context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame:
    short = int(params.get("short_window", 20))
    long = int(params.get("long_window", 120))
    return (context.prices.rolling(short).mean() > context.prices.rolling(long).mean()).astype(float)


def _buy_hold_signal(context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(1.0, index=context.prices.index, columns=context.prices.columns)


def _pe_momentum_signal(context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame:
    from qmt_quant.core.research.factors import load_pe_matrix
    from qmt_quant.storage.database import db_session

    with db_session() as conn:
        pe = load_pe_matrix(conn, context.prices.index, list(context.prices.columns))
    momentum = context.prices.pct_change(int(params.get("momentum_window", 20)))
    return ((pe <= float(params.get("pe_threshold", 30))) & (momentum > 0)).astype(float)


def _screening_signal(context: StrategyContext, params: Dict[str, Any]) -> pd.DataFrame:
    provider = context.metadata.get("selection_snapshot_provider")
    if provider is None:
        raise ValueError("screening_rebalance_requires_point_in_time_snapshots")
    rebalance_days = max(1, int(params.get("rebalance_days", 20)))
    signal = pd.DataFrame(0.0, index=context.prices.index, columns=context.prices.columns)
    selected: set[str] = set()
    audit_log = context.metadata.setdefault("selection_audit", [])
    for i, date in enumerate(context.prices.index):
        if i % rebalance_days == 0:
            if hasattr(provider, "snapshot_as_of"):
                snapshot = provider.snapshot_as_of(date.strftime("%Y-%m-%d"))
                selected = set(snapshot.codes)
                audit_log.extend(snapshot.audit_rows())
            else:
                selected = set(provider.codes_as_of(date))
                weight = 1 / len(selected) if selected else 0.0
                audit_log.extend(
                    {
                        "as_of_date": date.strftime("%Y-%m-%d"),
                        "code": code,
                        "factors": {},
                        "reason": "provider_selection",
                        "target_weight": weight,
                    }
                    for code in sorted(selected)
                )
        signal.loc[date, [code for code in selected if code in signal.columns]] = 1.0
    return signal


def _ma_candidates(params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    shorts = params.get("short_windows") or [5, 10, 20, 30]
    longs = params.get("long_windows") or [60, 120, 180, 250]
    return (
        {"short_window": int(short), "long_window": int(long)}
        for short in shorts
        for long in longs
        if int(short) < int(long)
    )


def _pe_momentum_candidates(params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    thresholds = params.get("pe_thresholds") or [15, 20, 30, 40]
    windows = params.get("momentum_windows") or [10, 20, 60]
    return (
        {"pe_threshold": float(threshold), "momentum_window": int(window)}
        for threshold in thresholds
        for window in windows
    )


def _screening_candidates(params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    days = params.get("rebalance_days_grid") or [5, 10, 20, 40]
    return ({"rebalance_days": int(day)} for day in days)


register_strategy(SignalStrategyPlugin("ma_cross", _ma_signal, _ma_candidates))
register_strategy(
    SignalStrategyPlugin("buy_hold", _buy_hold_signal, hold_only=True, include_first_bar=True)
)
register_strategy(SignalStrategyPlugin("pe_momentum", _pe_momentum_signal, _pe_momentum_candidates))
register_strategy(
    SignalStrategyPlugin("screening_rebalance", _screening_signal, _screening_candidates)
)
