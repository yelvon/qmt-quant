"""A-share venue rules (T+1, lot size, fees)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FillMode = Literal["next_open", "close"]


@dataclass
class FeeConfig:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.0005  # sell only
    transfer_fee_rate: float = 0.00001  # Shanghai only


@dataclass
class VenueRules:
    lot_size: int = 100
    t_plus_one: bool = True
    fees: FeeConfig = FeeConfig()


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


DEFAULT_VENUE = VenueRules()
