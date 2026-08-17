"""Trade service facade."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from qmt_quant.adapters.qmt.trader import QmtTrader
from qmt_quant.config import get_settings
from qmt_quant.core.trade.dry_run import _is_st_code, execute_orders
from qmt_quant.core.trade.risk import check_order
from qmt_quant.storage.database import db_session, run_migrations


def get_trade_status() -> Dict[str, Any]:
    settings = get_settings()
    trader = QmtTrader()
    connected = trader.connect()
    positions = trader.query_positions() if connected else []
    with db_session() as conn:
        orders = conn.execute(
            "SELECT * FROM live_order ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return {
        "connected": connected,
        "dry_run": settings.dry_run,
        "account_id": settings.account_id,
        "portfolio_value": trader.portfolio_value() if connected else settings.initial_cash,
        "positions": positions,
        "recent_orders": [dict(o) for o in orders],
    }


def flatten_trade_orders(
    *,
    codes: Optional[Sequence[str]] = None,
    side: str = "buy",
    quantity: int = 100,
    orders: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Prefer explicit `orders`; otherwise expand codes + side + quantity."""
    if orders:
        out: List[Dict[str, Any]] = []
        for raw in orders:
            out.append(
                {
                    "code": str(raw["code"]).strip(),
                    "side": str(raw.get("side") or side),
                    "quantity": int(raw.get("quantity") or quantity),
                }
            )
        return [row for row in out if row["code"]]
    return [{"code": c, "side": side, "quantity": quantity} for c in (codes or []) if c]


def preview_signal_orders(
    codes: Optional[List[str]] = None,
    side: str = "buy",
    quantity: int = 100,
    orders: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    raw = flatten_trade_orders(codes=codes, side=side, quantity=quantity, orders=orders)
    trader = QmtTrader()
    trader.connect()
    settings = get_settings()
    portfolio_value = trader.portfolio_value() if trader.connected else settings.initial_cash
    results: List[Dict[str, Any]] = []
    for item in raw:
        qty = int(item["quantity"])
        order_value = portfolio_value * 0.01
        is_st = _is_st_code(item["code"])
        ok, msg = check_order(
            code=item["code"],
            side=item["side"],
            quantity=qty,
            portfolio_value=portfolio_value,
            order_value=order_value,
            is_st=is_st,
        )
        results.append(
            {
                **item,
                "ok": ok,
                "reason": msg,
                "status": "ok" if ok else "rejected",
            }
        )
    return results


def submit_orders(orders: List[Dict[str, Any]], live: bool = False) -> List[Dict[str, Any]]:
    run_migrations()
    settings = get_settings()
    dry_run = settings.dry_run or not live
    return execute_orders(orders, dry_run=dry_run)
