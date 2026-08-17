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
        from qmt_quant.storage.instruments import get_name_map

        with db_session() as conn:
            names = get_name_map(conn, codes)
        return {code: str(name or "") for code, name in names.items()}
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
            rows.append({"code": code, "error": "insufficient_price_data", "bar_count": len(series)})
            continue

        sub_prices = prices[[code]]
        sub_ohlcv: pd.DataFrame | None = None
        if ohlcv is not None and not ohlcv.empty and "code" in ohlcv.columns:
            sub_ohlcv = ohlcv.loc[ohlcv["code"] == code].copy()

        try:
            sub_params = dict(params)
            sub_params.pop("portfolio", None)
            signal_prices = sub_params.get("signal_prices")
            if isinstance(signal_prices, pd.DataFrame) and code in signal_prices.columns:
                sub_params["signal_prices"] = signal_prices[[code]]
            signal_ohlcv = sub_params.get("signal_ohlcv")
            if (
                isinstance(signal_ohlcv, pd.DataFrame)
                and not signal_ohlcv.empty
                and "code" in signal_ohlcv.columns
            ):
                sub_params["signal_ohlcv"] = signal_ohlcv.loc[
                    signal_ohlcv["code"] == code
                ].copy()
            result = validator.run(strategy_id, sub_prices, ohlcv=sub_ohlcv, **sub_params)
        except Exception as exc:
            rows.append(
                {
                    "code": code,
                    "error": type(exc).__name__,
                    "message": str(exc)[:300],
                }
            )
            continue

        if not result.equity_curve:
            rows.append({"code": code, "error": "empty_equity_curve"})
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

    rows.sort(
        key=lambda r: (r.get("error") is None, r.get("total_return_pct", float("-inf")), r["code"]),
        reverse=True,
    )
    return rows
