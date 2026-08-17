"""Factor IC analysis for screening."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR
from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import load_financial_panel_asof

IC_TEMPLATE_FACTORS = {
    "low_pe": ("pe_inv", "momentum"),
    "ma_bull": ("momentum",),
}


def compute_factor_ic(
    *,
    template_id: str = "low_pe",
    sector: str = "沪深A股",
    horizons: Optional[List[int]] = None,
    frequency: str = "daily",
    quantiles: int = 5,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    horizons = horizons or [5, 20]
    factor_names = IC_TEMPLATE_FACTORS.get(template_id)
    if factor_names is None:
        raise ValueError(f"template {template_id!r} is not supported for factor IC")
    if job_id:
        report_job_progress(job_id, 0.12, "加载股票池行情…", step="load", detail=f"模板 {template_id}")
    codes = resolve_universe(sector)[:200]
    prices = load_price_matrix(codes=codes)
    if prices.empty:
        return {"error": "no_price_data"}
    if frequency == "weekly":
        prices = prices.resample("W-FRI").last().dropna(how="all")
    elif frequency != "daily":
        raise ValueError("frequency must be daily or weekly")

    columns = list(prices.columns)
    evaluation_dates = prices.index[:-max(horizons)]
    momentum = prices.pct_change(20).reindex(evaluation_dates)
    pe_inv = pd.DataFrame(index=evaluation_dates, columns=columns, dtype=float)
    total = len(evaluation_dates)
    with db_session() as conn:
        as_of_dates = [date.strftime("%Y-%m-%d") for date in evaluation_dates]
        financial_panel = load_financial_panel_asof(
            conn, "Pershareindex", columns, as_of_dates
        )
        for i, date in enumerate(evaluation_dates):
            if job_id and (i == 0 or i % 20 == 0 or i == total - 1):
                report_job_progress(
                    job_id,
                    0.2 + 0.45 * (i / max(total, 1)),
                    f"提取点时因子 {i + 1}/{total}",
                    step="factors",
                )
            as_of = date.strftime("%Y-%m-%d")
            for code in columns:
                fin = financial_panel.get(as_of, {}).get(code, {})
                pe = fin.get("pe") or fin.get("s_fa_pe")
                if pe is not None:
                    pe_inv.at[date, code] = -float(pe)

    if job_id:
        report_job_progress(job_id, 0.72, "计算 Spearman IC…", step="ic", detail=f"horizons {horizons}")
    analysis = analyze_rolling_ic(
        prices,
        {
            name: {"pe_inv": pe_inv, "momentum": momentum}[name]
            for name in factor_names
        },
        horizons=horizons,
        quantiles=quantiles,
    )
    if not analysis["ic"]:
        return {"error": "insufficient_data", "count": 0}

    payload = {
        "template": template_id,
        "sector": sector,
        "horizons": horizons,
        "frequency": frequency,
        "quantiles": quantiles,
        **analysis,
        "universe_size": len(columns),
        "point_in_time": {"financial_date_field": "announce_date", "strict_asof": True},
    }
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    out = reports_dir / f"ic_{template_id}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["result_path"] = str(out)
    return payload


def analyze_rolling_ic(
    prices: pd.DataFrame,
    factors: Dict[str, pd.DataFrame],
    *,
    horizons: List[int],
    quantiles: int = 5,
    min_cross_section: int = 3,
) -> Dict[str, Any]:
    """Analyze genuine cross-sectional forward returns at each observation date."""
    by_factor: Dict[str, Any] = {}
    legacy: Dict[str, Any] = {}
    for factor_name, panel in factors.items():
        horizon_results: Dict[str, Any] = {}
        for horizon in horizons:
            previous_groups: Dict[int, set[str]] = {}
            forward = prices.shift(-horizon).div(prices).sub(1)
            series_rows: List[Dict[str, Any]] = []
            group_returns: Dict[int, List[float]] = {q: [] for q in range(1, quantiles + 1)}
            turnovers: Dict[int, List[float]] = {q: [] for q in range(1, quantiles + 1)}
            samples = 0
            for date in panel.index.intersection(prices.index):
                cross = pd.concat(
                    [panel.loc[date].rename("factor"), forward.loc[date].rename("forward")],
                    axis=1,
                ).replace([np.inf, -np.inf], np.nan).dropna()
                if len(cross) < min_cross_section:
                    continue
                ic = _spearman(cross["factor"].to_numpy(), cross["forward"].to_numpy())
                if np.isnan(ic):
                    continue
                samples += len(cross)
                series_rows.append(
                    {"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "ic": round(float(ic), 6), "n": len(cross)}
                )
                ranks = cross["factor"].rank(method="first")
                bins = pd.qcut(ranks, min(quantiles, len(cross)), labels=False, duplicates="drop")
                for raw_group in sorted(bins.dropna().unique()):
                    q = int(raw_group) + 1
                    members = set(cross.index[bins == raw_group])
                    group_returns[q].append(float(cross.loc[list(members), "forward"].mean()))
                    previous = previous_groups.get(q)
                    if previous is not None:
                        overlap = len(previous & members) / max(len(previous), 1)
                        turnovers[q].append(1 - overlap)
                    previous_groups[q] = members
            values = pd.Series([row["ic"] for row in series_rows], dtype=float)
            mean = float(values.mean()) if not values.empty else 0.0
            std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            horizon_results[str(horizon)] = {
                "ic_series": series_rows,
                "ic_mean": round(mean, 6),
                "ic_std": round(std, 6),
                "icir": round(mean / std, 6) if std > 0 else 0.0,
                "samples": samples,
                "dates": len(series_rows),
                "quantile_returns": {
                    str(q): round(float(np.mean(rows)), 6) if rows else None
                    for q, rows in group_returns.items()
                },
                "turnover": {
                    str(q): round(float(np.mean(rows)), 6) if rows else 0.0
                    for q, rows in turnovers.items()
                },
            }
        valid_means = [
            result["ic_mean"] for result in horizon_results.values() if result["dates"] > 0
        ]
        decay_base = abs(valid_means[0]) if valid_means else 0.0
        decay = [
            {
                "horizon": int(horizon),
                "ic_mean": result["ic_mean"],
                "retention": round(abs(result["ic_mean"]) / decay_base, 6) if decay_base else 0.0,
            }
            for horizon, result in horizon_results.items()
        ]
        by_factor[factor_name] = {"horizons": horizon_results, "decay": decay}
        first = horizon_results.get(str(horizons[0]), {})
        if first.get("dates", 0):
            legacy[factor_name] = {
                key: first[key] for key in ("ic_mean", "ic_std", "icir", "samples", "dates")
            }
    return {"ic": legacy, "factors": by_factor}


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    try:
        from scipy.stats import spearmanr

        return float(spearmanr(x, y).correlation)
    except Exception:
        rx = pd.Series(x).rank()
        ry = pd.Series(y).rank()
        return float(rx.corr(ry))
