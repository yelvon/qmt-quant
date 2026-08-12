"""Dry-run trade execution."""

from __future__ import annotations

from typing import Any, Dict, List

from qmt_quant.adapters.qmt.trader import OrderRequest, QmtTrader
from qmt_quant.core.trade.risk import check_order
from qmt_quant.storage.database import db_session, run_migrations


def execute_orders(orders: List[Dict[str, Any]], dry_run: bool = True) -> List[Dict[str, Any]]:
    run_migrations()
    trader = QmtTrader()
    trader.connect()
    portfolio_value = trader.portfolio_value()
    results = []
    for raw in orders:
        req = OrderRequest(
            code=raw["code"],
            side=raw["side"],
            quantity=int(raw["quantity"]),
            price=raw.get("price"),
        )
        order_value = (req.price or 0) * req.quantity
        is_st = _is_st_code(req.code)
        ok, msg = check_order(
            code=req.code,
            side=req.side,
            quantity=req.quantity,
            portfolio_value=portfolio_value,
            order_value=order_value or portfolio_value * 0.01,
            is_st=is_st,
        )
        if not ok:
            results.append({"error": msg, **raw})
            continue
        out = trader.place_order(req, dry_run=dry_run)
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO live_order(order_id, code, side, price, quantity, status, dry_run)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    out.get("order_id"),
                    req.code,
                    req.side,
                    req.price,
                    req.quantity,
                    out.get("status"),
                    dry_run,
                ),
            )
        results.append(out)
    return results


def _is_st_code(code: str) -> bool:
    with db_session() as conn:
        row = conn.execute("SELECT is_st FROM instrument WHERE code=%s", (code,)).fetchone()
    if row is not None:
        return bool(row[0])
    return "ST" in code.upper()
