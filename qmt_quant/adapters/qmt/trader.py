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
        self._trader = None
        self._account = None
        self._account_type = "STOCK"

    def connect(self) -> bool:
        settings = get_settings()
        if not settings.userdata_path:
            try:
                from xtquant import xttrader  # type: ignore

                self._connected = True
                return True
            except ImportError:
                return False
        try:
            from xtquant.xttrader import XtQuantTrader  # type: ignore
            from xtquant.xttype import StockAccount  # type: ignore

            self._trader = XtQuantTrader(settings.userdata_path, session_id=1)
            self._trader.start()
            ok = self._trader.connect() == 0
            if ok and settings.account_id:
                self._account = StockAccount(settings.account_id, self._account_type)
                self._trader.subscribe(self._account)
            self._connected = ok
            return ok
        except ImportError:
            return False
        except Exception:
            return False

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
        if not self._connected or self._trader is None or self._account is None:
            raise RuntimeError("xttrader not connected")
        try:
            from xtquant import xtconstant  # type: ignore

            order_type = xtconstant.STOCK_BUY if req.side == "buy" else xtconstant.STOCK_SELL
            price_type = xtconstant.FIX_PRICE
            price = req.price or 0.0
            oid = self._trader.order_stock(
                self._account,
                req.code,
                order_type,
                req.quantity,
                price_type,
                price,
                "qmt-quant",
                "signal",
            )
            return {
                "order_id": str(oid),
                "code": req.code,
                "side": req.side,
                "quantity": req.quantity,
                "price": price,
                "status": "submitted",
                "dry_run": False,
            }
        except Exception as exc:
            return {
                "order_id": None,
                "code": req.code,
                "side": req.side,
                "status": "failed",
                "error": str(exc),
                "dry_run": False,
            }

    def query_positions(self) -> List[Dict[str, Any]]:
        if not self._connected or self._trader is None or self._account is None:
            return []
        try:
            positions = self._trader.query_stock_positions(self._account) or []
            return [
                {
                    "code": getattr(p, "stock_code", ""),
                    "quantity": getattr(p, "volume", 0),
                    "available": getattr(p, "can_use_volume", 0),
                    "cost": getattr(p, "open_price", 0),
                }
                for p in positions
            ]
        except Exception:
            return []

    def query_orders(self) -> List[Dict[str, Any]]:
        if not self._connected or self._trader is None or self._account is None:
            return []
        try:
            orders = self._trader.query_stock_orders(self._account) or []
            return [
                {
                    "order_id": getattr(o, "order_id", ""),
                    "code": getattr(o, "stock_code", ""),
                    "side": getattr(o, "order_type", ""),
                    "quantity": getattr(o, "volume", 0),
                    "status": getattr(o, "order_status", ""),
                }
                for o in orders
            ]
        except Exception:
            return []

    def portfolio_value(self) -> float:
        if not self._connected or self._trader is None or self._account is None:
            return get_settings().initial_cash
        try:
            asset = self._trader.query_stock_asset(self._account)
            if asset is None:
                return get_settings().initial_cash
            return float(getattr(asset, "total_asset", get_settings().initial_cash))
        except Exception:
            return get_settings().initial_cash
