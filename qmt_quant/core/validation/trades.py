"""Serialize validation trades for reports."""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

MULTI_SYMBOL_TRADE_CAP = 200


def serialize_trades(trades: Sequence[Any], n_symbols: int) -> Tuple[List[dict], bool]:
    """Keep all fills for a single symbol; cap multi-symbol reports."""
    rows = [_trade_row(t) for t in trades]
    if n_symbols <= 1:
        return rows, False
    if len(rows) <= MULTI_SYMBOL_TRADE_CAP:
        return rows, False
    return rows[:MULTI_SYMBOL_TRADE_CAP], True


def _trade_row(trade: Any) -> dict:
    if hasattr(trade, "__dict__"):
        return dict(trade.__dict__)
    if isinstance(trade, dict):
        return dict(trade)
    return {"value": trade}
