"""A-share validation backtester (Nautilus-compatible output shape)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.config import get_settings


@dataclass
class Trade:
    date: str
    code: str
    side: str
    price: float
    quantity: int
    fee: float


@dataclass
class ValidationResult:
    equity_curve: List[Dict[str, float]] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    verdict: str = "可以采用"
    trade_count: int = 0


class AShareDailyBacktester:
    """Event-driven daily backtester with T+1 and A-share fees."""

    def __init__(
        self,
        prices: pd.DataFrame,
        *,
        initial_cash: float | None = None,
        commission_rate: float | None = None,
        stamp_tax_rate: float | None = None,
        min_commission: float | None = None,
        match_price: str = "next_open",
    ) -> None:
        settings = get_settings()
        self.prices = prices.sort_index()
        self.dates = list(self.prices.index)
        self.initial_cash = initial_cash or settings.initial_cash
        self.commission_rate = commission_rate or settings.commission_rate
        self.stamp_tax_rate = stamp_tax_rate or settings.stamp_tax_rate
        self.min_commission = min_commission or settings.min_commission
        self.match_price = match_price
        self.cash = self.initial_cash
        self.positions: Dict[str, int] = {}
        self.buy_dates: Dict[str, pd.Timestamp] = {}
        self.trades: List[Trade] = []
        self.equity: List[Dict[str, float]] = []

    def run_ma_cross(self, short_window: int, long_window: int) -> ValidationResult:
        signal = pd.DataFrame(index=self.prices.index, columns=self.prices.columns, dtype=float)
        for code in self.prices.columns:
            s = self.prices[code]
            fast = s.rolling(short_window).mean()
            slow = s.rolling(long_window).mean()
            signal[code] = (fast > slow).astype(float)

        for i, dt in enumerate(self.dates):
            if i == 0:
                self._record_equity(dt)
                continue
            exec_idx = i if self.match_price == "close" else min(i, len(self.dates) - 1)
            exec_date = self.dates[exec_idx]
            for code in self.prices.columns:
                prev_sig = signal.iloc[i - 1][code]
                curr_sig = signal.iloc[i][code]
                price = float(self.prices.iloc[exec_idx][code])
                if np.isnan(price) or price <= 0:
                    continue
                pos = self.positions.get(code, 0)
                if prev_sig <= 0 and curr_sig > 0 and pos == 0:
                    qty = int(self.cash * 0.1 / price / 100) * 100
                    if qty >= 100:
                        self._buy(exec_date, code, price, qty)
                elif prev_sig > 0 and curr_sig <= 0 and pos > 0:
                    if self._can_sell(code, dt):
                        self._sell(exec_date, code, price, pos)
            self._record_equity(dt)

        return self._build_result()

    def _buy(self, dt: pd.Timestamp, code: str, price: float, qty: int) -> None:
        amount = price * qty
        fee = max(amount * self.commission_rate, self.min_commission)
        if self.cash < amount + fee:
            return
        self.cash -= amount + fee
        self.positions[code] = self.positions.get(code, 0) + qty
        self.buy_dates[code] = dt
        self.trades.append(
            Trade(dt.strftime("%Y-%m-%d"), code, "买入", price, qty, round(fee, 2))
        )

    def _sell(self, dt: pd.Timestamp, code: str, price: float, qty: int) -> None:
        amount = price * qty
        fee = max(amount * self.commission_rate, self.min_commission)
        tax = amount * self.stamp_tax_rate
        self.cash += amount - fee - tax
        self.positions[code] = 0
        self.buy_dates.pop(code, None)
        self.trades.append(
            Trade(dt.strftime("%Y-%m-%d"), code, "卖出", price, qty, round(fee + tax, 2))
        )

    def _can_sell(self, code: str, dt: pd.Timestamp) -> bool:
        bought = self.buy_dates.get(code)
        if bought is None:
            return True
        return dt > bought

    def _record_equity(self, dt: pd.Timestamp) -> None:
        mv = 0.0
        row = self.prices.loc[dt]
        for code, qty in self.positions.items():
            px = row.get(code)
            if px is not None and not np.isnan(px):
                mv += float(px) * qty
        total = self.cash + mv
        self.equity.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "equity": round(total / self.initial_cash * 100, 2),
            }
        )

    def _build_result(self) -> ValidationResult:
        if not self.equity:
            return ValidationResult()
        values = [e["equity"] for e in self.equity]
        total_return = values[-1] / 100 - 1
        peak = values[0]
        max_dd = 0.0
        for v in values:
            peak = max(peak, v)
            max_dd = min(max_dd, v / peak - 1)
        verdict = "可以采用"
        if total_return < 0:
            verdict = "不建议"
        elif max_dd < -0.2:
            verdict = "建议复核"
        return ValidationResult(
            equity_curve=self.equity,
            trades=self.trades,
            total_return_pct=round(total_return * 100, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            verdict=verdict,
            trade_count=len(self.trades),
        )
