"""Factor IC analysis for screening."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import load_financial_asof


def compute_factor_ic(
    *,
    template_id: str = "low_pe",
    sector: str = "沪深A股",
    horizons: Optional[List[int]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    horizons = horizons or [5, 20]
    codes = resolve_universe(sector)[:200]
    prices = load_price_matrix(codes=codes)
    if prices.empty:
        return {"error": "no_price_data"}

    factor_rows: List[Dict[str, float]] = []
    with db_session() as conn:
        as_of = prices.index[-1].strftime("%Y-%m-%d")
        for code in prices.columns:
            fin = load_financial_asof(conn, "Pershareindex", code, as_of) or {}
            pe = fin.get("pe") or fin.get("s_fa_pe")
            if pe is None:
                continue
            mom = float(prices[code].pct_change(20).iloc[-1] or 0)
            factor_rows.append({"code": code, "pe_inv": -float(pe), "momentum": mom})

    if len(factor_rows) < 10:
        return {"error": "insufficient_data", "count": len(factor_rows)}

    rets = {h: prices.pct_change(h).iloc[-1] for h in horizons}
    ic_results = {}
    for factor in ("pe_inv", "momentum"):
        values = []
        for row in factor_rows:
            code = row["code"]
            if code not in prices.columns:
                continue
            for h in horizons:
                fwd = rets[h].get(code)
                if fwd is not None and not np.isnan(fwd):
                    values.append((row[factor], float(fwd)))
        if len(values) < 10:
            continue
        x = np.array([v[0] for v in values])
        y = np.array([v[1] for v in values])
        ic = _spearman(x, y)
        ic_results[factor] = {"ic_mean": round(float(ic), 4), "samples": len(values)}

    payload = {
        "template": template_id,
        "sector": sector,
        "horizons": horizons,
        "ic": ic_results,
        "universe_size": len(factor_rows),
    }
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    out = reports_dir / f"ic_{template_id}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["result_path"] = str(out)
    return payload


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    try:
        from scipy.stats import spearmanr

        return float(spearmanr(x, y).correlation)
    except Exception:
        rx = pd.Series(x).rank()
        ry = pd.Series(y).rank()
        return float(rx.corr(ry))
