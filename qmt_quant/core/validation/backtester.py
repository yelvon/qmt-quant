"""A-share validation backtester (Nautilus-compatible output shape)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.core.backtest.strategy import (
    STRATEGIES,
    BacktestResult,
    CostModel,
    PortfolioSpec,
    StrategyContext,
)
from qmt_quant.core.validation.venue_cn_a_share import (
    DEFAULT_VENUE,
    FeeConfig,
    daily_price_limit_ratio,
    match_buy,
    match_sell,
    round_lots,
)


@dataclass
class Trade:
    date: str
    code: str
    side: str
    price: float
    quantity: int
    fee: float


ValidationResult = BacktestResult


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
        signal_prices: pd.DataFrame | None = None,
        signal_ohlcv: pd.DataFrame | None = None,
        initial_cash: float | None = None,
        commission_rate: float | None = None,
        stamp_tax_rate: float | None = None,
        min_commission: float | None = None,
        transfer_fee_rate: float | None = None,
        slippage_bps: float | None = None,
        match_price: str = "next_open",
        enforce_limit: bool = True,
        position_size_pct: float = 0.1,
        cost_model: CostModel | None = None,
        portfolio: PortfolioSpec | None = None,
    ) -> None:
        cost_model = cost_model or CostModel.from_settings()
        portfolio = portfolio or PortfolioSpec.from_settings(
            initial_cash=initial_cash,
            position_size_pct=position_size_pct,
            match_price=match_price,
            enforce_limit=enforce_limit,
        )
        self.prices = prices.sort_index()
        self.ohlcv = ohlcv
        if self.ohlcv is not None and "date" in self.ohlcv.columns:
            self.ohlcv = self.ohlcv.copy()
            self.ohlcv["date"] = pd.to_datetime(self.ohlcv["date"])
            self.ohlcv = self.ohlcv.set_index("date", drop=False).sort_index()
        self.signal_prices = (
            signal_prices.sort_index() if signal_prices is not None else self.prices
        )
        self.signal_ohlcv = signal_ohlcv if signal_ohlcv is not None else self.ohlcv
        self.dates = list(self.prices.index)
        self.initial_cash = portfolio.initial_cash
        self.fees = FeeConfig(
            commission_rate=commission_rate if commission_rate is not None else cost_model.commission_rate,
            min_commission=min_commission if min_commission is not None else cost_model.min_commission,
            stamp_duty_rate=stamp_tax_rate if stamp_tax_rate is not None else cost_model.stamp_duty_rate,
            transfer_fee_rate=(
                transfer_fee_rate if transfer_fee_rate is not None else cost_model.transfer_fee_rate
            ),
        )
        self.slippage_bps = slippage_bps if slippage_bps is not None else cost_model.slippage_bps
        self.match_price = portfolio.match_price
        self.enforce_limit = portfolio.enforce_limit
        self.position_size_pct = min(max(float(portfolio.position_size_pct), 0.01), 1.0)
        self.venue = DEFAULT_VENUE
        self.cash = self.initial_cash
        self.positions: Dict[str, int] = {}
        self.buy_dates: Dict[str, pd.Timestamp] = {}
        self.trades: List[Trade] = []
        self.equity: List[Dict[str, float]] = []
        self.skipped_signals: List[Dict[str, str]] = []
        self.selection_audit: List[Dict[str, Any]] = []

    def run_ma_cross(self, short_window: int, long_window: int) -> ValidationResult:
        return self.run_strategy(
            "ma_cross", {"short_window": short_window, "long_window": long_window}
        )

    def run_buy_hold(self) -> ValidationResult:
        return self.run_strategy("buy_hold")

    def run_pe_momentum(
        self,
        *,
        pe_threshold: float = 30,
        momentum_window: int = 20,
    ) -> ValidationResult:
        return self.run_strategy(
            "pe_momentum",
            {"pe_threshold": pe_threshold, "momentum_window": momentum_window},
        )

    def run_screening_rebalance(
        self,
        screen_run_id: str | None,
        *,
        rebalance_days: int = 20,
    ) -> ValidationResult:
        return self.run_strategy(
            "screening_rebalance",
            {"screen_run_id": screen_run_id, "rebalance_days": rebalance_days},
        )

    def run_strategy(
        self,
        strategy_id: str,
        params: Dict[str, Any] | None = None,
        *,
        metadata: Dict[str, Any] | None = None,
    ) -> BacktestResult:
        plugin = STRATEGIES.get(strategy_id)
        runtime_metadata = dict(metadata or {})
        runtime_metadata["selection_audit"] = self.selection_audit
        context = StrategyContext(
            prices=self.signal_prices,
            ohlcv=self.signal_ohlcv,
            cost_model=CostModel(
                commission_rate=self.fees.commission_rate,
                min_commission=self.fees.min_commission,
                stamp_duty_rate=self.fees.stamp_duty_rate,
                transfer_fee_rate=self.fees.transfer_fee_rate,
                slippage_bps=self.slippage_bps,
            ),
            portfolio=PortfolioSpec(
                initial_cash=self.initial_cash,
                position_size_pct=self.position_size_pct,
                match_price=self.match_price,
                enforce_limit=self.enforce_limit,
            ),
            metadata=runtime_metadata,
        )
        try:
            signal = plugin.signal(context, params or {})
        except ValueError as exc:
            return BacktestResult(
                verdict="建议复核",
                skipped_signals=[{"date": "", "code": "", "reason": str(exc)}],
            )
        return self._run_signal_loop(
            self._expand_signal_to_execution_calendar(signal),
            hold_only=bool(getattr(plugin, "hold_only", False)),
            include_first_bar=bool(getattr(plugin, "include_first_bar", False)),
        )

    def _expand_signal_to_execution_calendar(self, signal: pd.DataFrame) -> pd.DataFrame:
        """Expose a completed signal bar only from its actual close date onward."""
        signal = signal.reindex(columns=self.prices.columns).sort_index()
        if signal.index.equals(self.prices.index):
            return signal
        # Weekly labels are actual last trading dates. Reindexing then forward
        # filling makes the new state visible at that day's close; the existing
        # next_open loop executes it on the next daily row.
        return signal.reindex(self.prices.index).ffill().fillna(0.0)

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
        result.skipped_signals = skipped + list(result.skipped_signals or [])
        return result

    def _run_signal_loop(
        self,
        signal: pd.DataFrame,
        *,
        hold_only: bool = False,
        include_first_bar: bool = False,
    ) -> ValidationResult:
        for exec_idx, exec_date in enumerate(self.dates):
            signal_idx = exec_idx if self.match_price == "close" else exec_idx - 1
            if signal_idx < 0 or (signal_idx == 0 and not include_first_bar):
                self._record_equity(exec_date)
                continue
            for code in self.prices.columns:
                prev_sig = 0.0 if signal_idx == 0 else signal.iloc[signal_idx - 1][code]
                curr_sig = signal.iloc[signal_idx][code]
                exec_price = self._exec_price(code, exec_idx)
                if exec_price is None or exec_price <= 0:
                    continue
                pos = self.positions.get(code, 0)
                if prev_sig <= 0 and curr_sig > 0 and pos == 0:
                    if self._is_suspended(code, exec_idx):
                        self._skip(exec_date, code, "suspended_volume_zero")
                        continue
                    if self._limit_blocks_buy(code, exec_idx):
                        continue
                    qty = round_lots(
                        self.cash * self.position_size_pct / exec_price, self.venue.lot_size
                    )
                    if qty >= self.venue.lot_size:
                        self._buy(exec_date, code, exec_price, qty)
                    else:
                        self._skip(exec_date, code, "insufficient_cash_for_lot")
                elif not hold_only and prev_sig > 0 and curr_sig <= 0 and pos > 0:
                    if self._is_suspended(code, exec_idx):
                        self._skip(exec_date, code, "suspended_volume_zero")
                        continue
                    if self._can_sell(code, exec_date) and not self._limit_blocks_sell(code, exec_idx):
                        self._sell(exec_date, code, exec_price, pos)
            self._record_equity(exec_date)
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

    def _is_suspended(self, code: str, exec_idx: int) -> bool:
        if self.ohlcv is None:
            return False
        dt = self.dates[exec_idx]
        try:
            rows = self.ohlcv[
                (self.ohlcv["code"] == code)
                & (
                    (self.ohlcv["date"] == dt.strftime("%Y-%m-%d"))
                    | (self.ohlcv.index == dt)
                )
            ]
            if rows.empty or "volume" not in rows.columns:
                return False
            volume = rows.iloc[0].get("volume")
            return volume is not None and not pd.isna(volume) and float(volume) <= 0
        except (KeyError, TypeError, AttributeError, ValueError):
            return False

    def _skip(self, dt: pd.Timestamp, code: str, reason: str) -> None:
        self.skipped_signals.append(
            {"date": dt.strftime("%Y-%m-%d"), "code": code, "reason": reason}
        )

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
        ratio = daily_price_limit_ratio(
            code, self.dates[exec_idx].strftime("%Y-%m-%d"), is_st=self._bar_is_st(code, exec_idx)
        )
        limit = pre * (1 + ratio)
        return high >= limit * 0.999

    def _at_limit_down(self, code: str, exec_idx: int) -> bool:
        pre, _ = self._pre_close_high(code, exec_idx)
        low = self._bar_low(code, exec_idx)
        if pre is None or low is None or pre <= 0:
            return False
        ratio = daily_price_limit_ratio(
            code, self.dates[exec_idx].strftime("%Y-%m-%d"), is_st=self._bar_is_st(code, exec_idx)
        )
        limit = pre * (1 - ratio)
        return low <= limit * 1.001

    def _bar_is_st(self, code: str, exec_idx: int) -> bool:
        if self.ohlcv is None:
            return False
        dt = self.dates[exec_idx]
        try:
            rows = self.ohlcv[
                (self.ohlcv["code"] == code)
                & ((self.ohlcv["date"] == dt.strftime("%Y-%m-%d")) | (self.ohlcv.index == dt))
            ]
            if rows.empty:
                return False
            row = rows.iloc[0]
            if "is_st" in row and not pd.isna(row["is_st"]):
                return bool(row["is_st"])
            return "ST" in str(row.get("name") or "").upper()
        except (KeyError, TypeError, AttributeError):
            return False

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
        fill = match_buy(
            cash=self.cash,
            budget=price * qty,
            price=price,
            code=code,
            fees=self.fees,
            lot_size=self.venue.lot_size,
        )
        if fill is None:
            self._skip(dt, code, "insufficient_cash_for_lot")
            return
        self.cash += fill.cash_delta
        self.positions[code] = self.positions.get(code, 0) + fill.quantity
        self.buy_dates[code] = dt
        self.trades.append(
            Trade(
                dt.strftime("%Y-%m-%d"),
                code,
                "买入",
                round(price, 4),
                fill.quantity,
                round(fill.fee, 2),
            )
        )

    def _sell(self, dt: pd.Timestamp, code: str, price: float, qty: int) -> None:
        price = self._apply_slippage(price, "sell")
        available = self.positions.get(code, 0)
        fill = match_sell(
            available=available, quantity=qty, price=price, code=code, fees=self.fees
        )
        if fill is None:
            return
        self.cash += fill.cash_delta
        self.positions[code] = available - fill.quantity
        self.buy_dates.pop(code, None)
        self.trades.append(
            Trade(
                dt.strftime("%Y-%m-%d"),
                code,
                "卖出",
                round(price, 4),
                fill.quantity,
                round(fill.fee, 2),
            )
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
                "cash": round(self.cash, 8),
                "market_value": round(mv, 8),
                "equity_value": round(total, 8),
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
            skipped_signals=self.skipped_signals,
            selection_audit=self.selection_audit,
        )
