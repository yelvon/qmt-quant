"""xttrader adapter (dry-run safe)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from qmt_quant.config import get_settings


@dataclass
class OrderRequest:
    code: str
    side: str  # buy | sell
    quantity: int
    price: Optional[float] = None


class QmtTrader:
    def __init__(self) -> None:
        self._connected = False
        self._xttrader = None

    def connect(self) -> bool:
        settings = get_settings()
        try:
            from xtquant import xttrader  # type: ignore

            self._xttrader = xttrader
            self._connected = True
            return True
        except ImportError:
            return bool(settings.userdata_path)

    @property
    def connected(self) -> bool:
        return self._connected

    def place_order(self, req: OrderRequest, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run or get_settings().dry_run:
            return {
                "order_id": f"DRY-{req.code}-{req.side}",
                "code": req.code,
                "side": req.side,
                "quantity": req.quantity,
                "price": req.price,
                "status": "simulated",
                "dry_run": True,
            }
        if not self._connected:
            raise RuntimeError("xttrader not connected")
        return {
            "order_id": "LIVE-PENDING",
            "code": req.code,
            "side": req.side,
            "quantity": req.quantity,
            "status": "submitted",
            "dry_run": False,
        }

    def query_positions(self) -> List[Dict[str, Any]]:
        return []

    def query_orders(self) -> List[Dict[str, Any]]:
        return []
