"""Trade service facade."""

from __future__ import annotations

from typing import Any, Dict, List

from qmt_quant.adapters.qmt.trader import QmtTrader
from qmt_quant.config import get_settings
from qmt_quant.core.trade.dry_run import execute_orders
from qmt_quant.storage.database import db_session, run_migrations


def get_trade_status() -> Dict[str, Any]:
    settings = get_settings()
    trader = QmtTrader()
    connected = trader.connect()
    with db_session() as conn:
        orders = conn.execute(
            "SELECT * FROM live_order ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return {
        "connected": connected,
        "dry_run": settings.dry_run,
        "account_id": settings.account_id,
        "recent_orders": [dict(o) for o in orders],
    }


def preview_signal_orders(
    codes: List[str],
    side: str = "buy",
    quantity: int = 100,
) -> List[Dict[str, Any]]:
    return [{"code": c, "side": side, "quantity": quantity} for c in codes]


def submit_orders(orders: List[Dict[str, Any]], live: bool = False) -> List[Dict[str, Any]]:
    run_migrations()
    settings = get_settings()
    dry_run = settings.dry_run or not live
    return execute_orders(orders, dry_run=dry_run)
