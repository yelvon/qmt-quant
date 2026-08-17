"""Reproducible experiment artifacts, metrics and diagnostics."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from qmt_quant.config import ROOT_DIR
from qmt_quant.core.backtest.strategy import STRATEGIES


METRIC_KEYS = (
    "total_return_pct", "annualized_return_pct", "max_drawdown_pct",
    "max_drawdown_duration_days", "annualized_volatility_pct", "sharpe",
    "sortino", "calmar", "benchmark_excess_return_pct", "information_ratio",
    "turnover", "fee_ratio_pct", "win_rate_pct", "profit_loss_ratio",
    "concentration",
)


def strategy_identity(strategy_id: str) -> tuple[str, str]:
    """Return a stable strategy version and source hash without inventing one."""
    try:
        plugin = STRATEGIES.get(strategy_id)
        cls = type(plugin)
        source = inspect.getsource(cls)
        version = str(getattr(plugin, "version", None) or getattr(cls, "version", None) or "unversioned")
    except Exception:
        source, version = strategy_id, "unversioned"
    return version, hashlib.sha256(source.encode("utf-8")).hexdigest()


def data_fingerprint(
    prices: pd.DataFrame, *, adjust: str, frequency: str
) -> Dict[str, Any]:
    content_hash = hashlib.sha256()
    content_hash.update(pd.util.hash_pandas_object(prices.index, index=False).values.tobytes())
    content_hash.update(pd.util.hash_pandas_object(prices, index=True).values.tobytes())
    return {
        "bar_start": prices.index.min().strftime("%Y-%m-%d") if len(prices.index) else None,
        "bar_end": prices.index.max().strftime("%Y-%m-%d") if len(prices.index) else None,
        "bar_count": int(prices.notna().sum().sum()),
        "time_count": int(len(prices.index)),
        "instrument_count": int(len(prices.columns)),
        "adjust": adjust,
        "frequency": frequency,
        "columns_hash": hashlib.sha256(
            "\n".join(sorted(map(str, prices.columns))).encode("utf-8")
        ).hexdigest(),
        "content_hash": content_hash.hexdigest(),
    }


def compute_metrics(
    equity_curve: Sequence[Mapping[str, Any]],
    *,
    benchmark_curve: Sequence[Mapping[str, Any]] | None = None,
    trades: Sequence[Mapping[str, Any]] | None = None,
    positions: Sequence[Mapping[str, Any]] | None = None,
    periods_per_year: int = 252,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {key: None for key in METRIC_KEYS}
    if len(equity_curve) < 2:
        return metrics
    frame = pd.DataFrame(equity_curve)
    value_col = "equity" if "equity" in frame else "value"
    if value_col not in frame:
        return metrics
    if "date" in frame:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").set_index("date")
    values = pd.to_numeric(frame[value_col], errors="coerce").dropna()
    if len(values) < 2 or float(values.iloc[0]) == 0:
        return metrics
    returns = values.pct_change().dropna()
    total = float(values.iloc[-1] / values.iloc[0] - 1)
    years = len(returns) / periods_per_year
    annual = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else None
    running_max = values.cummax()
    drawdowns = values / running_max - 1
    max_dd = float(drawdowns.min())
    underwater = drawdowns < 0
    groups = (~underwater).cumsum()
    duration = int(underwater.groupby(groups).sum().max()) if underwater.any() else 0
    vol = float(returns.std(ddof=1) * math.sqrt(periods_per_year)) if len(returns) > 1 else None
    downside = returns[returns < 0]
    downside_dev = float(downside.std(ddof=1) * math.sqrt(periods_per_year)) if len(downside) > 1 else None
    metrics.update({
        "total_return_pct": total * 100,
        "annualized_return_pct": annual * 100 if annual is not None else None,
        "max_drawdown_pct": max_dd * 100,
        "max_drawdown_duration_days": duration,
        "annualized_volatility_pct": vol * 100 if vol is not None else None,
        "sharpe": annual / vol if annual is not None and vol and vol > 0 else None,
        "sortino": annual / downside_dev if annual is not None and downside_dev and downside_dev > 0 else None,
        "calmar": annual / abs(max_dd) if annual is not None and max_dd < 0 else None,
    })
    if benchmark_curve:
        bench = pd.DataFrame(benchmark_curve)
        if value_col in bench or "equity" in bench:
            if "date" in bench:
                bench["date"] = pd.to_datetime(bench["date"], errors="coerce")
                bench = bench.dropna(subset=["date"]).drop_duplicates("date", keep="last").set_index("date")
            bvals = pd.to_numeric(bench.get(value_col, bench.get("equity")), errors="coerce").dropna()
            if len(bvals) >= 2 and float(bvals.iloc[0]) != 0:
                bret = bvals.pct_change().dropna()
                metrics["benchmark_excess_return_pct"] = (
                    total - float(bvals.iloc[-1] / bvals.iloc[0] - 1)
                ) * 100
                aligned = pd.concat(
                    [returns.rename("strategy"), bret.rename("benchmark")], axis=1, join="inner"
                ).dropna()
                active = aligned["strategy"] - aligned["benchmark"]
                tracking = float(active.std(ddof=1)) if len(active) > 1 else 0
                metrics["information_ratio"] = (
                    float(active.mean() / tracking * math.sqrt(periods_per_year))
                    if tracking > 0 else None
                )
    _trade_metrics(metrics, trades or [], average_equity=float(values.mean()))
    _position_metrics(metrics, positions or [])
    return {k: _finite(v) for k, v in metrics.items()}


def _trade_metrics(
    metrics: Dict[str, Any],
    trades: Sequence[Mapping[str, Any]],
    *,
    average_equity: float,
) -> None:
    if not trades:
        return
    pnls = [float(t["pnl"]) for t in trades if t.get("pnl") is not None]
    fees = [float(t["fee"]) for t in trades if t.get("fee") is not None]
    notionals = []
    for trade in trades:
        if trade.get("notional") is not None:
            notionals.append(abs(float(trade["notional"])))
        elif trade.get("price") is not None and trade.get("quantity") is not None:
            notionals.append(abs(float(trade["price"]) * float(trade["quantity"])))
    if pnls:
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
        metrics["win_rate_pct"] = len(wins) / len(pnls) * 100
        metrics["profit_loss_ratio"] = (
            float(np.mean(wins) / abs(np.mean(losses))) if wins and losses else None
        )
    if notionals:
        traded = sum(notionals)
        metrics["turnover"] = traded / average_equity if average_equity > 0 else None
        metrics["fee_ratio_pct"] = sum(fees) / traded * 100 if fees and traded > 0 else None


def _position_metrics(metrics: Dict[str, Any], positions: Sequence[Mapping[str, Any]]) -> None:
    weights = [abs(float(p["weight"])) for p in positions if p.get("weight") is not None]
    if weights:
        total = sum(weights)
        metrics["concentration"] = sum((w / total) ** 2 for w in weights) if total else None


def build_diagnostics(
    equity_curve: Sequence[Mapping[str, Any]],
    *,
    stock_returns: Sequence[Mapping[str, Any]] | None = None,
    positions: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "stock_contributions": list(stock_returns or []),
        "drawdown_periods": [],
        "annual_returns": {},
        "monthly_returns": {},
        "capital_utilization": None,
        "industry_exposure": None,
        "industry_exposure_note": "无可靠行业分类数据，未输出行业暴露",
    }
    if len(equity_curve) >= 2:
        f = pd.DataFrame(equity_curve)
        f["date"] = pd.to_datetime(f["date"])
        f["equity"] = pd.to_numeric(f["equity"], errors="coerce")
        f = f.dropna().set_index("date")
        ret = f["equity"].pct_change().dropna()
        out["annual_returns"] = {str(k): _finite(v * 100) for k, v in ret.groupby(ret.index.year).apply(lambda x: (1 + x).prod() - 1).items()}
        out["monthly_returns"] = {str(k): _finite(v * 100) for k, v in ret.groupby(ret.index.to_period("M")).apply(lambda x: (1 + x).prod() - 1).items()}
        dd = f["equity"] / f["equity"].cummax() - 1
        active = dd < 0
        for _, group in f.assign(dd=dd, active=active).groupby((~active).cumsum()):
            under = group[group["active"]]
            if not under.empty:
                trough = under["dd"].idxmin()
                out["drawdown_periods"].append({
                    "start": under.index[0].strftime("%Y-%m-%d"),
                    "trough": trough.strftime("%Y-%m-%d"),
                    "end": under.index[-1].strftime("%Y-%m-%d"),
                    "drawdown_pct": _finite(float(under["dd"].min()) * 100),
                })
    weights = [abs(float(p["weight"])) for p in (positions or []) if p.get("weight") is not None]
    if weights:
        out["capital_utilization"] = _finite(float(np.mean(weights)))
    return out


def write_artifacts(
    run_id: str,
    *,
    manifest: Mapping[str, Any],
    detail: Mapping[str, Any],
    equity: Sequence[Mapping[str, Any]] | None = None,
    trades: Sequence[Mapping[str, Any]] | None = None,
    positions: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, str]:
    directory = ROOT_DIR / "reports" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "manifest": directory / "manifest.json",
        "detail": directory / "detail.json",
        "equity": directory / "equity.json",
        "trades": directory / "trades.json",
        "positions": directory / "positions.json",
    }
    payloads = {
        "manifest": manifest, "detail": detail, "equity": list(equity or []),
        "trades": list(trades or []), "positions": list(positions or []),
    }
    for key, path in files.items():
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payloads[key], ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(path)
    return {"artifact_dir": str(directory), **{k: str(v) for k, v in files.items()}}


def _finite(value: Any) -> Any:
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    return value
