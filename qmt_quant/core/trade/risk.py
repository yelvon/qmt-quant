"""Risk checks before live orders."""

from __future__ import annotations

from typing import List, Tuple

from qmt_quant.config import get_settings


def check_order(
    *,
    code: str,
    side: str,
    quantity: int,
    portfolio_value: float,
    order_value: float,
    is_st: bool = False,
) -> Tuple[bool, str]:
    settings = get_settings()
    if is_st:
        return False, "ST 标的禁止下单"
    if quantity % 100 != 0:
        return False, "数量必须为 100 股整数倍"
    max_value = portfolio_value * settings.max_weight_per_symbol
    if order_value > max_value:
        return False, f"单笔仓位超过上限 {settings.max_weight_per_symbol:.0%}"
    if side not in ("buy", "sell"):
        return False, "side 必须为 buy 或 sell"
    return True, "ok"


def filter_allowed(codes: List[str], st_codes: List[str]) -> List[str]:
    st_set = set(st_codes)
    return [c for c in codes if c not in st_set]
