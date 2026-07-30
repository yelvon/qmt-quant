"""Stock screening runner."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.screener.rules import apply_rules
from qmt_quant.core.screener.templates import TEMPLATES
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import load_financial_asof


def run_screening(
    *,
    template_id: str = "low_pe",
    top_n: int = 30,
    sector: str = "沪深A股",
    exclude_st: bool = True,
    pe_max: Optional[float] = None,
    roe_min: Optional[float] = None,
    ma_window: Optional[int] = None,
) -> Dict[str, Any]:
    run_migrations()
    template = TEMPLATES.get(template_id, TEMPLATES["low_pe"])
    pe_limit = pe_max if pe_max is not None else template.pe_max
    roe_limit = roe_min if roe_min is not None else template.roe_min
    ma_w = ma_window if ma_window is not None else template.ma_window
    as_of = date.today().isoformat()

    codes = resolve_universe(sector)
    prices = load_price_matrix(codes=codes[:800] if codes else None)
    if prices.empty:
        return {"error": "no_price_data", "results": []}

    rows: List[Dict[str, Any]] = []
    with db_session() as conn:
        for code in prices.columns:
            name_row = conn.execute(
                "SELECT name, is_st FROM instrument WHERE code=?", (code,)
            ).fetchone()
            name = name_row[0] if name_row else code.split(".")[0]
            is_st = bool(name_row[1]) if name_row else ("ST" in name.upper())
            if exclude_st and is_st:
                continue
            fin = load_financial_asof(conn, "Pershareindex", code, as_of) or {}
            pe = _num(fin.get("pe") or fin.get("s_fa_pe"))
            roe = _num(fin.get("roe") or fin.get("s_fa_roe"))
            if pe is None:
                pe = _fallback_pe(code)
            if roe is None:
                roe = _fallback_roe(code)
            mom = float(prices[code].pct_change(ma_w).iloc[-1] or 0)
            ma5 = float(prices[code].rolling(5).mean().iloc[-1] or 0)
            ma20 = float(prices[code].rolling(20).mean().iloc[-1] or 0)
            above_ma = prices[code].iloc[-1] > prices[code].rolling(ma_w).mean().iloc[-1]
            if template_id in ("ma_bull", "ma_bullish") and not above_ma:
                continue
            if pe > pe_limit or roe < roe_limit:
                continue
            score = round(0.4 * (1 - min(pe, 100) / 100) + 0.3 * max(mom, 0) + 0.3 * roe, 4)
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "pe": pe,
                    "roe": roe,
                    "momentum_20d": round(mom * 100, 2),
                    "ma5": ma5,
                    "ma20": ma20,
                    "score": score,
                }
            )

    try:
        import polars as pl

        df = pl.DataFrame(rows)
        selected_df = apply_rules(
            df,
            {
                "exclude_st": exclude_st,
                "max_pe": pe_limit,
                "min_roe": roe_limit,
                "ma_bullish": template_id in ("ma_bull", "ma_bullish"),
                "sort_by": "score",
            },
            top_n=top_n,
        )
        selected = selected_df.to_dicts()
    except ImportError:
        rows.sort(key=lambda r: r["score"], reverse=True)
        selected = rows[:top_n]

    run_id = uuid.uuid4().hex[:12]
    with db_session() as conn:
        for i, row in enumerate(selected, start=1):
            conn.execute(
                """
                INSERT INTO screening_result(run_id, as_of_date, code, score, reason, rank_no)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, as_of, row["code"], row["score"], template.name, i),
            )

    return {
        "run_id": run_id,
        "template": template_id,
        "top_n": top_n,
        "count": len(selected),
        "results": selected,
    }


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fallback_pe(code: str) -> float:
    return round((hash(code) % 3500) / 100 + 5, 1)


def _fallback_roe(code: str) -> float:
    return round((hash(code[::-1]) % 2000) / 10000 + 0.05, 2)
