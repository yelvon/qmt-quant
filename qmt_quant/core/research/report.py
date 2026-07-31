"""Research report helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


def summarize_combos(combos: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    sorted_rows = sorted(combos, key=lambda r: r.get("total_return_pct", 0), reverse=True)
    return sorted_rows[:top_n]


def heatmap_payload(combos: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "categories": [c.get("label", "") for c in combos],
        "values": [c.get("total_return_pct", 0) for c in combos],
    }


def build_quantstats_summary(equity_by_date: Mapping[str, float]) -> Dict[str, Any]:
    if len(equity_by_date) < 2:
        return {}
    dates = sorted(equity_by_date.keys())
    values = [equity_by_date[d] for d in dates]
    rets = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            rets.append(values[i] / values[i - 1] - 1)
    if not rets:
        return {}
    try:
        import pandas as pd

        series = pd.Series(rets, index=pd.to_datetime(dates[1:]))
        import quantstats as qs

        return {
            "sharpe": round(float(qs.stats.sharpe(series, periods=252)), 3),
            "max_drawdown_pct": round(float(qs.stats.max_drawdown(series)) * 100, 2),
            "win_rate_pct": round(float(qs.stats.win_rate(series)) * 100, 2),
            "volatility_pct": round(float(qs.stats.volatility(series, periods=252)) * 100, 2),
        }
    except Exception:
        total = values[-1] / values[0] - 1
        peak = values[0]
        max_dd = 0.0
        wins = sum(1 for r in rets if r > 0)
        for v in values:
            peak = max(peak, v)
            max_dd = min(max_dd, v / peak - 1)
        return {
            "sharpe": None,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "win_rate_pct": round(wins / len(rets) * 100, 2),
            "total_return_pct": round(total * 100, 2),
        }
