"""NautilusTrader MA cross strategy."""

from __future__ import annotations

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy


class MACrossConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType | None = None
    short_window: int = 20
    long_window: int = 120
    trade_size: int = 100


class MACrossStrategy(Strategy):
    def __init__(self, config: MACrossConfig) -> None:
        super().__init__(config)
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type or BarType.from_str(
            f"{config.instrument_id}-1-DAY-LAST-EXTERNAL"
        )
        self.short_window = config.short_window
        self.long_window = config.long_window
        self.trade_size = config.trade_size
        self.closes: list[float] = []

    def on_start(self) -> None:
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar) -> None:
        self.closes.append(float(bar.close))
        if len(self.closes) < self.long_window:
            return
        short_ma = sum(self.closes[-self.short_window :]) / self.short_window
        long_ma = sum(self.closes[-self.long_window :]) / self.long_window
        pos = self.cache.positions(instrument_id=self.instrument_id)
        has_pos = bool(pos)
        if short_ma > long_ma and not has_pos:
            self.submit_market_order(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.trade_size,
            )
        elif short_ma < long_ma and has_pos:
            self.close_all_positions(self.instrument_id)
