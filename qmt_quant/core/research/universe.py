"""Research / validation universe resolution — keep scan and validate on the same stocks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from qmt_quant.config import get_settings
from qmt_quant.core.screener.bridge import load_codes_by_run_id
from qmt_quant.core.sync.universe import resolve_universe

TURNOVER_LOOKBACK_BARS = 20
WATCHLIST_SECTORS = ("watchlist", "我的自选池")


def _normalize_sample(sample: Optional[str]) -> str:
    value = str(sample or "all").strip().lower()
    return value if value in {"all", "turnover"} else "all"


def _cap_n(universe_n: Optional[int]) -> Optional[int]:
    try:
        n = int(universe_n) if universe_n is not None else None
    except (TypeError, ValueError):
        n = None
    return n if n is not None and n > 0 else None


def _explicit_pool(
    *,
    strategy_id: str,
    codes: Optional[List[str]],
    screen_run_id: Optional[str],
    sector: str,
) -> bool:
    if screen_run_id or codes:
        return True
    if sector in WATCHLIST_SECTORS:
        return True
    if strategy_id == "screening_rebalance":
        return True
    return False


def rank_codes_by_turnover(universe: List[str], amounts: Dict[str, float], n: int) -> List[str]:
    """Order by summed amount descending; empty if no positive turnover."""
    scored = [(float(amounts.get(code) or 0), idx, code) for idx, code in enumerate(universe)]
    if not any(amt > 0 for amt, _, _ in scored):
        return []
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [code for _, _, code in scored[:n]]


def load_turnover_sums(
    universe: List[str],
    *,
    range_end: Optional[str] = None,
    adjust_type: Optional[str] = None,
    lookback: int = TURNOVER_LOOKBACK_BARS,
) -> Dict[str, float]:
    if not universe:
        return {}
    from qmt_quant.storage.database import db_session

    adj = adjust_type or get_settings().bar_adjust_type
    end = range_end
    with db_session() as conn:
        if end:
            rows = conn.execute(
                """
                WITH recent AS (
                    SELECT DISTINCT date
                    FROM daily_bar
                    WHERE adjust_type = %s AND date <= %s
                    ORDER BY date DESC
                    LIMIT %s
                )
                SELECT b.code, COALESCE(SUM(b.amount), 0)
                FROM daily_bar b
                INNER JOIN recent r ON b.date = r.date
                WHERE b.adjust_type = %s AND b.code = ANY(%s)
                GROUP BY b.code
                """,
                (adj, end, lookback, adj, list(universe)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                WITH recent AS (
                    SELECT DISTINCT date
                    FROM daily_bar
                    WHERE adjust_type = %s
                    ORDER BY date DESC
                    LIMIT %s
                )
                SELECT b.code, COALESCE(SUM(b.amount), 0)
                FROM daily_bar b
                INNER JOIN recent r ON b.date = r.date
                WHERE b.adjust_type = %s AND b.code = ANY(%s)
                GROUP BY b.code
                """,
                (adj, lookback, adj, list(universe)),
            ).fetchall()
    return {str(code): float(amt or 0) for code, amt in rows}


def resolve_research_universe_meta(
    *,
    sector: str = "沪深A股",
    strategy_id: str = "ma_cross",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
    sample: str = "all",
    universe_n: Optional[int] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    adjust_type: Optional[str] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    sample_mode = _normalize_sample(sample)
    cap_n = _cap_n(universe_n)
    meta: Dict[str, Any] = {
        "sample": sample_mode,
        "universe_n": cap_n,
        "sample_fallback": None,
        "sampled": False,
    }

    if screen_run_id:
        universe = load_codes_by_run_id(screen_run_id)
    elif codes:
        universe = list(codes)
    else:
        universe = resolve_universe(sector)
        if sector in WATCHLIST_SECTORS:
            universe = resolve_universe("watchlist")
    universe = sorted(dict.fromkeys(universe or []))
    from qmt_quant.core.universe import filter_universe_as_of

    universe = filter_universe_as_of(universe, range_start)

    if _explicit_pool(
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
        sector=sector,
    ):
        meta["universe_n"] = len(universe)
        meta["sample"] = "all"
        return universe, meta

    if not universe:
        return [], meta

    if cap_n is None:
        meta["universe_n"] = len(universe)
        return universe, meta

    meta["sampled"] = len(universe) > cap_n
    if sample_mode == "turnover":
        # Rank only with information available at the backtest start. Ranking at
        # range_end is a liquidity look-ahead.
        amounts = load_turnover_sums(universe, range_end=range_start, adjust_type=adjust_type)
        ranked = rank_codes_by_turnover(universe, amounts, cap_n)
        if ranked:
            return ranked, meta
        meta["sample_fallback"] = "code_order"
        meta["sample"] = "all"
    return list(universe[:cap_n]), meta


def resolve_research_universe(
    *,
    sector: str = "沪深A股",
    strategy_id: str = "ma_cross",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
    sample: str = "all",
    universe_n: Optional[int] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    adjust_type: Optional[str] = None,
) -> List[str]:
    """Return the code list research would load (before price matrix fetch)."""
    used, _meta = resolve_research_universe_meta(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
        sample=sample,
        universe_n=universe_n,
        range_start=range_start,
        range_end=range_end,
        adjust_type=adjust_type,
    )
    return used


def describe_research_universe(
    *,
    sector: str = "沪深A股",
    strategy_id: str = "ma_cross",
    codes: Optional[List[str]] = None,
    screen_run_id: Optional[str] = None,
    sample: str = "all",
    universe_n: Optional[int] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
) -> dict:
    """Pool size vs actual research/backtest size."""
    if screen_run_id:
        pool = load_codes_by_run_id(screen_run_id)
    elif codes:
        pool = list(codes)
    else:
        pool = resolve_universe(sector)
        if sector in WATCHLIST_SECTORS:
            pool = resolve_universe("watchlist")
    pool = list(pool or [])
    used, meta = resolve_research_universe_meta(
        sector=sector,
        strategy_id=strategy_id,
        codes=codes,
        screen_run_id=screen_run_id,
        sample=sample,
        universe_n=universe_n,
        range_start=range_start,
        range_end=range_end,
    )
    used_n = len(used)
    sampled = bool(meta.get("sampled"))
    fallback = meta.get("sample_fallback")
    sample_mode = meta.get("sample") or "all"
    if sampled and sample_mode == "turnover" and not fallback:
        sample_label = f"近{TURNOVER_LOOKBACK_BARS}日成交额前 {used_n}"
    elif sampled:
        sample_label = f"确定性代码序前 {used_n}"
    else:
        sample_label = "全部标的"
    cap = None if not sampled else meta.get("universe_n")
    return {
        "pool_size": len(pool),
        "used": used_n,
        "capped": sampled and len(pool) > used_n,
        "cap": cap,
        "sample": sample_mode,
        "sample_fallback": fallback,
        "sample_label": sample_label,
        "universe_n": meta.get("universe_n"),
    }


def universe_from_research_run(research: dict) -> Optional[List[str]]:
    """Resolve validation universe from a saved research backtest_run row."""
    params = research.get("params") or {}
    stored = params.get("codes")
    if stored:
        return [str(c) for c in stored if c]
    range_end = None
    preset = params.get("range_preset")
    if preset:
        from qmt_quant.core.presets import resolve_range_preset

        range_start, range_end = resolve_range_preset(str(preset))
    else:
        range_start = None
    return resolve_research_universe(
        sector=str(params.get("sector") or "沪深A股"),
        strategy_id=str(research.get("strategy_id") or "ma_cross"),
        screen_run_id=params.get("screen_run_id"),
        sample=str(params.get("sample") or "all"),
        universe_n=params.get("universe_n"),
        range_start=range_start,
        range_end=range_end,
    )
