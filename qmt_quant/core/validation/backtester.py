"""A-share validation backtester (Nautilus-compatible output shape)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.core.screener.bridge import load_codes_by_run_id
from qmt_quant.core.validation.venue_cn_a_share import (
    DEFAULT_VENUE,
    FeeConfig,
    commission,
    round_lots,
    stamp_duty,
    transfer_fee,
)


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
    skipped_signals: List[Dict[str, str]] = field(default_factory=list)


def parse_signal_side(raw: Any) -> Optional[str]:
    s = str(raw or "").strip().lower()
    if s in ("buy", "b", "买入"):
        return "buy"
    if s in ("sell", "s", "卖出"):
        return "sell"
    return None


class AShareDailyBacktester:
    """Event-driven daily backtester with T+1 and A-share fees."""

    def __init__(
        self,
        prices: pd.DataFrame,
        *,
        ohlcv: pd.DataFrame | None = None,
        initial_cash: float | None = None,
        commission_rate: float | None = None,
        stamp_tax_rate: float | None = None,
        min_commission: float | None = None,
        transfer_fee_rate: float | None = None,
        slippage_bps: float | None = None,
        match_price: str = "next_open",
        enforce_limit: bool = True,
        position_size_pct: float = 0.1,
    ) -> None:
        settings = get_settings()
        self.prices = prices.sort_index()
        self.ohlcv = ohlcv
        self.dates = list(self.prices.index)
        self.initial_cash = initial_cash or settings.initial_cash
        self.fees = FeeConfig(
            commission_rate=commission_rate or settings.commission_rate,
            min_commission=min_commission or settings.min_commission,
            stamp_duty_rate=stamp_tax_rate or settings.stamp_tax_rate,
            transfer_fee_rate=transfer_fee_rate or settings.transfer_fee_rate,
        )
        self.slippage_bps = slippage_bps if slippage_bps is not None else settings.slippage_bps
        self.match_price = match_price
        self.enforce_limit = enforce_limit
        self.position_size_pct = min(max(float(position_size_pct), 0.01), 1.0)
        self.venue = DEFAULT_VENUE
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
        return self._run_signal_loop(signal)

    def run_buy_hold(self) -> ValidationResult:
        signal = pd.DataFrame(1.0, index=self.prices.index, columns=self.prices.columns)
        return self._run_signal_loop(signal, hold_only=True)

    def run_pe_momentum(
        self,
        *,
        pe_threshold: float = 30,
        momentum_window: int = 20,
    ) -> ValidationResult:
        from qmt_quant.core.research.factors import load_pe_matrix
        from qmt_quant.storage.database import db_session

        with db_session() as conn:
            pe_mat = load_pe_matrix(conn, self.prices.index, list(self.prices.columns))
        mom = self.prices.pct_change(momentum_window)
        signal = ((pe_mat <= pe_threshold) & (mom > 0)).astype(float)
        return self._run_signal_loop(signal)

    def run_screening_rebalance(
        self,
        screen_run_id: str | None,
        *,
        rebalance_days: int = 20,
    ) -> ValidationResult:
        codes = load_codes_by_run_id(screen_run_id) if screen_run_id else []
        if not codes:
            return ValidationResult(verdict="建议复核")
        signal = pd.DataFrame(0.0, index=self.prices.index, columns=self.prices.columns)
        valid = [c for c in codes if c in signal.columns]
        if not valid:
            return ValidationResult(verdict="建议复核")
        for i in range(0, len(self.dates), rebalance_days):
            dt = self.dates[i]
            for c in valid:
                signal.loc[dt:, c] = 1.0
        return self._run_signal_loop(signal)

    def run_signals(self, signals: list | None) -> ValidationResult:
        """Replay explicit buy/sell dates on the first price column (single-stock)."""
        skipped: List[Dict[str, str]] = []
        signal = pd.DataFrame(0.0, index=self.prices.index, columns=self.prices.columns)
        if self.prices.empty:
            result = ValidationResult(verdict="建议复核")
            result.skipped_signals = skipped
            return result
        code = self.prices.columns[0]
        date_index = {dt.strftime("%Y-%m-%d"): dt for dt in self.dates}
        held = 0.0
        for item in signals or []:
            if not isinstance(item, dict):
                skipped.append({"date": "", "reason": "invalid_row"})
                continue
            date_s = str(item.get("date") or "")[:10]
            side = parse_signal_side(item.get("side"))
            if side is None:
                skipped.append({"date": date_s, "reason": "invalid_side"})
                continue
            ts = date_index.get(date_s)
            if ts is None:
                skipped.append({"date": date_s, "reason": "no_bar"})
                continue
            held = 1.0 if side == "buy" else 0.0
            signal.loc[ts:, code] = held
        result = self._run_signal_loop(signal, include_first_bar=True)
        result.skipped_signals = skipped
        return result

    def _run_signal_loop(
        self,
        signal: pd.DataFrame,
        *,
        hold_only: bool = False,
        include_first_bar: bool = False,
    ) -> ValidationResult:
        for i, dt in enumerate(self.dates):
            if i == 0 and not include_first_bar:
                self._record_equity(dt)
                continue
            exec_idx = self._exec_index(i)
            if exec_idx is None:
                self._record_equity(dt)
                continue
            exec_date = self.dates[exec_idx]
            for code in self.prices.columns:
                prev_sig = 0.0 if i == 0 else signal.iloc[i - 1][code]
                curr_sig = signal.iloc[i][code]
                exec_price = self._exec_price(code, exec_idx)
                if exec_price is None or exec_price <= 0:
                    continue
                pos = self.positions.get(code, 0)
                if prev_sig <= 0 and curr_sig > 0 and pos == 0:
                    if self._limit_blocks_buy(code, exec_idx):
                        continue
                    qty = round_lots(
                        self.cash * self.position_size_pct / exec_price, self.venue.lot_size
                    )
                    if qty >= self.venue.lot_size:
                        self._buy(exec_date, code, exec_price, qty)
                elif not hold_only and prev_sig > 0 and curr_sig <= 0 and pos > 0:
                    if self._can_sell(code, dt) and not self._limit_blocks_sell(code, exec_idx):
                        self._sell(exec_date, code, exec_price, pos)
            self._record_equity(dt)
        return self._build_result()

    def _exec_index(self, signal_idx: int) -> int | None:
        if self.match_price == "close":
            return signal_idx
        nxt = signal_idx + 1
        return nxt if nxt < len(self.dates) else None

    def _exec_price(self, code: str, exec_idx: int) -> float | None:
        if self.ohlcv is not None and self.match_price == "next_open":
            try:
                row = self.ohlcv.loc[self.dates[exec_idx]]
                if isinstance(row, pd.DataFrame):
                    row = row[row["code"] == code].iloc[0]
                px = float(row.get("open") or row.get("close") or self.prices.iloc[exec_idx][code])
            except (KeyError, IndexError, TypeError):
                px = float(self.prices.iloc[exec_idx][code])
        else:
            px = float(self.prices.iloc[exec_idx][code])
        if np.isnan(px):
            return None
        return px

    def _apply_slippage(self, price: float, side: str) -> float:
        slip = self.slippage_bps / 10000.0
        if side == "buy":
            return price * (1 + slip)
        return price * (1 - slip)

    def _limit_blocks_buy(self, code: str, exec_idx: int) -> bool:
        if not self.enforce_limit or self.ohlcv is None:
            return False
        return self._at_limit_up(code, exec_idx)

    def _limit_blocks_sell(self, code: str, exec_idx: int) -> bool:
        if not self.enforce_limit or self.ohlcv is None:
            return False
        return self._at_limit_down(code, exec_idx)

    def _at_limit_up(self, code: str, exec_idx: int) -> bool:
        pre, high = self._pre_close_high(code, exec_idx)
        if pre is None or high is None or pre <= 0:
            return False
        limit = pre * 1.1 if not code.startswith("3") else pre * 1.2
        return high >= limit * 0.999

    def _at_limit_down(self, code: str, exec_idx: int) -> bool:
        pre, _ = self._pre_close_high(code, exec_idx)
        low = self._bar_low(code, exec_idx)
        if pre is None or low is None or pre <= 0:
            return False
        limit = pre * 0.9 if not code.startswith("3") else pre * 0.8
        return low <= limit * 1.001

    def _pre_close_high(self, code: str, exec_idx: int) -> tuple[float | None, float | None]:
        dt = self.dates[exec_idx]
        try:
            row = self.ohlcv[(self.ohlcv["code"] == code) & (self.ohlcv["date"] == dt.strftime("%Y-%m-%d"))]
            if row.empty:
                row = self.ohlcv[(self.ohlcv["code"] == code) & (self.ohlcv.index == dt)]
            if row.empty:
                return None, None
            r = row.iloc[0]
            return float(r.get("pre_close") or 0) or None, float(r.get("high") or 0) or None
        except (KeyError, TypeError, AttributeError):
            return None, None

    def _bar_low(self, code: str, exec_idx: int) -> float | None:
        dt = self.dates[exec_idx]
        try:
            row = self.ohlcv[(self.ohlcv["code"] == code) & (self.ohlcv["date"] == dt.strftime("%Y-%m-%d"))]
            if row.empty:
                return None
            return float(row.iloc[0].get("low") or 0) or None
        except (KeyError, TypeError, AttributeError):
            return None

    def _buy(self, dt: pd.Timestamp, code: str, price: float, qty: int) -> None:
        price = self._apply_slippage(price, "buy")
        amount = price * qty
        comm = commission(amount, self.fees)
        xfer = transfer_fee(amount, code, self.fees)
        fee = comm + xfer
        if self.cash < amount + fee:
            return
        self.cash -= amount + fee
        self.positions[code] = self.positions.get(code, 0) + qty
        self.buy_dates[code] = dt
        self.trades.append(
            Trade(dt.strftime("%Y-%m-%d"), code, "买入", round(price, 4), qty, round(fee, 2))
        )

    def _sell(self, dt: pd.Timestamp, code: str, price: float, qty: int) -> None:
        price = self._apply_slippage(price, "sell")
        amount = price * qty
        comm = commission(amount, self.fees)
        tax = stamp_duty(amount, self.fees)
        xfer = transfer_fee(amount, code, self.fees)
        fee = comm + tax + xfer
        self.cash += amount - fee
        self.positions[code] = 0
        self.buy_dates.pop(code, None)
        self.trades.append(
            Trade(dt.strftime("%Y-%m-%d"), code, "卖出", round(price, 4), qty, round(fee, 2))
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
