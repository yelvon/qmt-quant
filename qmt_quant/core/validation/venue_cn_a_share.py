"""A-share venue rules (T+1, lot size, fees)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

FillMode = Literal["next_open", "close"]


@dataclass
class FeeConfig:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.001  # sell only, matches settings default
    transfer_fee_rate: float = 0.00001  # Shanghai only


@dataclass
class VenueRules:
    lot_size: int = 100
    t_plus_one: bool = True
    fees: FeeConfig = field(default_factory=FeeConfig)


@dataclass(frozen=True)
class Fill:
    quantity: int
    price: float
    fee: float
    cash_delta: float


def commission(amount: float, fees: FeeConfig) -> float:
    return max(amount * fees.commission_rate, fees.min_commission)


def stamp_duty(amount: float, fees: FeeConfig) -> float:
    return amount * fees.stamp_duty_rate


def transfer_fee(amount: float, code: str, fees: FeeConfig) -> float:
    if code.endswith(".SH"):
        return amount * fees.transfer_fee_rate
    return 0.0


def round_lots(shares: float, lot_size: int = 100) -> int:
    return int(shares // lot_size) * lot_size


def daily_price_limit_ratio(
    code: str,
    trade_date: str | date,
    *,
    is_st: bool = False,
) -> float:
    """Return the regulatory daily limit ratio using conservative known history."""
    if is_st:
        return 0.05
    raw = code.split(".")[0]
    day = date.fromisoformat(str(trade_date)[:10])
    if raw.startswith(("4", "8", "92")):  # 北交所及历史新三板代码
        return 0.30
    if raw.startswith("688"):  # 科创板
        return 0.20
    if raw.startswith("3"):  # 创业板注册制切换
        return 0.20 if day >= date(2020, 8, 24) else 0.10
    return 0.10


def match_buy(
    *,
    cash: float,
    budget: float,
    price: float,
    code: str,
    fees: FeeConfig,
    lot_size: int = 100,
) -> Fill | None:
    """Pure buy matcher; quantity is lot-aligned and all-in cost never exceeds cash."""
    if cash < 0 or budget <= 0 or price <= 0 or lot_size <= 0:
        return None
    quantity = round_lots(min(cash, budget) / price, lot_size)
    while quantity >= lot_size:
        amount = price * quantity
        fee = commission(amount, fees) + transfer_fee(amount, code, fees)
        if amount + fee <= cash + 1e-9:
            return Fill(quantity, price, fee, -(amount + fee))
        quantity -= lot_size
    return None


def match_sell(
    *, available: int, quantity: int, price: float, code: str, fees: FeeConfig
) -> Fill | None:
    """Pure sell matcher; it cannot sell more than the available position."""
    quantity = min(max(int(quantity), 0), max(int(available), 0))
    if quantity <= 0 or price <= 0:
        return None
    amount = price * quantity
    fee = commission(amount, fees) + stamp_duty(amount, fees) + transfer_fee(amount, code, fees)
    return Fill(quantity, price, fee, amount - fee)


DEFAULT_VENUE = VenueRules()
