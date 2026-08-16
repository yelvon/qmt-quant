"""Per-stock validation returns for multi-code backtests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.validation.engine import CustomValidationEngine
from qmt_quant.storage.database import db_session


def _fetch_instrument_names(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    try:
        with db_session() as conn:
            placeholders = ",".join(["%s"] * len(codes))
            rows = conn.execute(
                f"SELECT code, name FROM instrument WHERE code IN ({placeholders})",
                tuple(codes),
            ).fetchall()
        return {str(code): str(name or "") for code, name in rows}
    except Exception:
        return {}


def compute_per_stock_returns(
    *,
    strategy_id: str,
    prices: pd.DataFrame,
    ohlcv: pd.DataFrame | None,
    codes: List[str],
    match_price: str,
    slippage_bps: float,
    params: Dict[str, Any],
    job_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run isolated full-position backtests per code (same strategy params).

    Only meaningful for multi-stock pools. Each stock gets its own account with
    ``position_size_pct=1.0``, unlike the portfolio run which shares cash at 10% slices.
    """
    ordered = [str(c) for c in codes if str(c) in prices.columns]
    if len(ordered) <= 1:
        return []

    validator = CustomValidationEngine(
        match_price=match_price,
        slippage_bps=slippage_bps,
        position_size_pct=1.0,
    )
    rows: List[Dict[str, Any]] = []
    total = len(ordered)

    for i, code in enumerate(ordered):
        if job_id and (i == 0 or (i + 1) % 5 == 0 or i + 1 == total):
            report_job_progress(
                job_id,
                0.72 + 0.05 * (i / max(total, 1)),
                "逐股回测…",
                step="compare",
                detail=f"{i + 1}/{total} · {code}",
            )

        series = prices[code].dropna()
        if len(series) < 5:
            continue

        sub_prices = prices[[code]]
        sub_ohlcv: pd.DataFrame | None = None
        if ohlcv is not None and not ohlcv.empty and "code" in ohlcv.columns:
            sub_ohlcv = ohlcv.loc[ohlcv["code"] == code].copy()

        try:
            result = validator.run(strategy_id, sub_prices, ohlcv=sub_ohlcv, **params)
        except Exception:
            continue

        if not result.equity_curve:
            continue

        rows.append(
            {
                "code": code,
                "total_return_pct": result.total_return_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "trade_count": result.trade_count,
            }
        )

    if not rows:
        return []

    names = _fetch_instrument_names([r["code"] for r in rows])
    for row in rows:
        row["name"] = names.get(row["code"], "")

    rows.sort(key=lambda r: (r["total_return_pct"], r["code"]), reverse=True)
    return rows
