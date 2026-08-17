"""Research / validation universe resolution — keep scan and validate on the same stocks."""

from __future__ import annotations

from typing import List, Optional

from qmt_quant.core.screener.bridge import load_codes_by_run_id
from qmt_quant.core.sync.universe import resolve_universe

RESEARCH_UNIVERSE_CAP = 50


def resolve_research_universe(
    *,
    sector: str = "沪深A股",
    strategy_id: str = "ma_cross",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
) -> List[str]:
    """Return the code list research would load (before price matrix fetch)."""
    if screen_run_id:
        universe = load_codes_by_run_id(screen_run_id)
    elif codes:
        universe = list(codes)
    else:
        universe = resolve_universe(sector)
        if sector in ("watchlist", "我的自选池"):
            universe = resolve_universe("watchlist")
    cap = None if strategy_id == "screening_rebalance" else RESEARCH_UNIVERSE_CAP
    if cap and universe:
        return list(universe[:cap])
    return list(universe) if universe else []


def describe_research_universe(
    *,
    sector: str = "沪深A股",
    strategy_id: str = "ma_cross",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
) -> dict:
    """Pool size vs actual research/backtest size (does not change sampling)."""
    if screen_run_id:
        pool = load_codes_by_run_id(screen_run_id)
    elif codes:
        pool = list(codes)
    else:
        pool = resolve_universe(sector)
        if sector in ("watchlist", "我的自选池"):
            pool = resolve_universe("watchlist")
    pool = list(pool or [])
    used = resolve_research_universe(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
    )
    cap = None if strategy_id == "screening_rebalance" else RESEARCH_UNIVERSE_CAP
    used_n = len(used)
    return {
        "pool_size": len(pool),
        "used": used_n,
        "capped": cap is not None and len(pool) > used_n,
        "cap": cap,
    }


def universe_from_research_run(research: dict) -> Optional[List[str]]:
    """Resolve validation universe from a saved research backtest_run row."""
    params = research.get("params") or {}
    stored = params.get("codes")
    if stored:
        return [str(c) for c in stored if c]
    return resolve_research_universe(
        sector=str(params.get("sector") or "沪深A股"),
        strategy_id=str(research.get("strategy_id") or "ma_cross"),
        screen_run_id=params.get("screen_run_id"),
    )
