"""Bar gap detection and repair planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from qmt_quant.config import get_settings
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.sync.calendar import list_trade_dates_between
from qmt_quant.core.sync.universe import load_watchlist
from qmt_quant.storage.bars import bar_counts_by_code, index_bar_dates, latest_bar_dates, market_latest_date
from qmt_quant.storage.database import db_session


@dataclass
class RepairPlan:
    mode: str = "targeted"
    sector: str = "沪深A股"
    adjust_type: str = "front"
    codes: List[str] = field(default_factory=list)
    date_ranges: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "RepairPlan":
        return cls(
            mode=str(data.get("mode", "targeted")),
            sector=str(data.get("sector", "沪深A股")),
            adjust_type=str(data.get("adjust_type", "front")),
            codes=[str(c) for c in (data.get("codes") or [])],
            date_ranges=[
                {"start": str(r["start"]), "end": str(r["end"])}
                for r in (data.get("date_ranges") or [])
            ],
        )


def _trading_day_lag(latest: str, market_latest: str, trade_dates: List[str]) -> int:
    if latest >= market_latest:
        return 0
    between = [d for d in trade_dates if latest < d <= market_latest]
    return len(between)


def _median_completeness(
    conn,
    codes: Sequence[str],
    range_start: str,
    range_end: str,
    adjust_type: str,
    trade_dates: List[str],
) -> float:
    if not codes or not trade_dates:
        return 0.0
    expected = len(trade_dates)
    counts = bar_counts_by_code(conn, range_start, range_end, adjust_type, codes)
    ratios = []
    for code in codes:
        cnt = counts.get(code, 0)
        ratios.append(cnt / expected if expected else 0.0)
    ratios.sort()
    mid = len(ratios) // 2
    if not ratios:
        return 0.0
    if len(ratios) % 2:
        return round(ratios[mid], 4)
    return round((ratios[mid - 1] + ratios[mid]) / 2, 4)


def _missing_market_dates(
    conn,
    trade_dates: List[str],
    adjust_type: str,
    lookback_days: int = 30,
) -> List[str]:
    if not trade_dates:
        return []
    window = trade_dates[-lookback_days:] if len(trade_dates) > lookback_days else trade_dates
    if not window:
        return []
    have = set(index_bar_dates(conn, start=window[0], end=window[-1], adjust_type=adjust_type))
    return [d for d in window if d not in have]


def scan_stale_codes(
    conn,
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    stale_trading_days: Optional[int] = None,
    max_codes: int = 200,
) -> Tuple[List[str], str, int]:
    settings = get_settings()
    stale_days = stale_trading_days if stale_trading_days is not None else settings.sync_stale_trading_days
    market_latest = market_latest_date(conn, adjust_type)
    if not market_latest:
        return [], "", 0

    trade_dates = list_trade_dates_between(
        (date.fromisoformat(market_latest) - timedelta(days=120)).isoformat(),
        market_latest,
    )
    if not trade_dates:
        trade_dates = [market_latest]

    latest_map = latest_bar_dates(conn, adjust_type)
    inst_rows = conn.execute(
        "SELECT code, delist_date FROM instrument ORDER BY code"
    ).fetchall()
    if not inst_rows:
        inst_rows = [(c, None) for c in latest_map]

    stale: List[Tuple[str, int]] = []
    today = date.today().isoformat()
    for row in inst_rows:
        code = row[0]
        delist = row[1]
        if delist and str(delist)[:10] < today:
            continue
        latest = latest_map.get(code)
        if not latest:
            stale.append((code, 9999))
            continue
        lag = _trading_day_lag(latest, market_latest, trade_dates)
        if lag > stale_days:
            stale.append((code, lag))

    stale.sort(key=lambda x: -x[1])
    codes = [c for c, _ in stale[:max_codes]]
    return codes, market_latest, len(stale)


def build_repair_plan(
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    codes: Optional[Sequence[str]] = None,
    lookback: Optional[str] = None,
    max_codes: Optional[int] = None,
    missing_market_dates: Optional[Sequence[str]] = None,
    market_latest: Optional[str] = None,
    lag_days: int = 0,
) -> RepairPlan:
    settings = get_settings()
    cap = max_codes if max_codes is not None else settings.sync_auto_repair_max_codes
    with db_session() as conn:
        mkt = market_latest or market_latest_date(conn, adjust_type) or date.today().isoformat()
        if codes:
            target_codes = list(codes)[:cap]
        else:
            target_codes, _, _ = scan_stale_codes(
                conn, sector=sector, adjust_type=adjust_type, max_codes=cap
            )

        if not target_codes:
            from qmt_quant.core.sync.universe import resolve_universe

            universe = resolve_universe(sector)
            if missing_market_dates:
                target_codes = universe[:cap]
                start = min(missing_market_dates)
                end = max(missing_market_dates)
                return RepairPlan(
                    sector=sector,
                    adjust_type=adjust_type,
                    codes=target_codes,
                    date_ranges=[{"start": start, "end": end}],
                )
            if lag_days > 1 and universe:
                target_codes = universe[:cap]
                repair_start = (
                    date.fromisoformat(mkt) - timedelta(days=lag_days + 5)
                ).isoformat()
                return RepairPlan(
                    sector=sector,
                    adjust_type=adjust_type,
                    codes=target_codes,
                    date_ranges=[{"start": repair_start, "end": mkt}],
                )
            return RepairPlan(sector=sector, adjust_type=adjust_type)

        latest_map = latest_bar_dates(conn, adjust_type)
        watchlist = set(load_watchlist())
        if watchlist and not codes:
            prioritized = [c for c in target_codes if c in watchlist]
            rest = [c for c in target_codes if c not in watchlist]
            target_codes = (prioritized + rest)[:cap]

        starts: List[str] = []
        for code in target_codes:
            latest = latest_map.get(code)
            if latest:
                starts.append(latest)
        lookback_preset = lookback or settings.sync_gap_scan_lookback
        range_start, _ = resolve_range_preset(lookback_preset, max_date=mkt)
        repair_start = min(starts) if starts else range_start
        if repair_start > mkt:
            repair_start = range_start

        return RepairPlan(
            mode="targeted",
            sector=sector,
            adjust_type=adjust_type,
            codes=target_codes,
            date_ranges=[{"start": repair_start, "end": mkt}],
        )


def analyze_gaps(
    *,
    sector: str = "沪深A股",
    adjust_type: str = "front",
    detailed: bool = False,
    as_of_date: Optional[str] = None,
) -> Dict[str, object]:
    settings = get_settings()
    as_of = as_of_date or date.today().isoformat()
    lookback_preset = settings.sync_gap_scan_lookback
    with db_session() as conn:
        market_latest = market_latest_date(conn, adjust_type)
        range_start, range_end = resolve_range_preset(lookback_preset, max_date=market_latest or as_of)
        trade_dates = list_trade_dates_between(range_start, range_end or as_of)
        if not trade_dates and market_latest:
            trade_dates = [market_latest]

        stale_codes, _, stale_total = scan_stale_codes(conn, sector=sector, adjust_type=adjust_type)
        missing_market = _missing_market_dates(conn, trade_dates, adjust_type)

        inst_count = conn.execute("SELECT COUNT(*) FROM instrument").fetchone()[0]
        latest_map = latest_bar_dates(conn, adjust_type)
        bar_codes = len(latest_map)
        coverage_pct = round((bar_codes / inst_count * 100), 1) if inst_count else 0.0

        lag_days = 0
        if market_latest and trade_dates:
            ref = trade_dates[-1]
            if market_latest < ref:
                lag_days = _trading_day_lag(market_latest, ref, trade_dates)

        stale_pct = round((stale_total / inst_count * 100), 2) if inst_count else 0.0
        completeness_median = 0.0
        if detailed and stale_codes:
            sample = stale_codes[:50] + [c for c in load_watchlist() if c in latest_map][:20]
            sample = list(dict.fromkeys(sample))
            completeness_median = _median_completeness(
                conn, sample, range_start, range_end or as_of, adjust_type, trade_dates
            )

        repair_plan = build_repair_plan(
            sector=sector,
            adjust_type=adjust_type,
            codes=stale_codes if stale_codes else None,
            missing_market_dates=missing_market,
            market_latest=market_latest,
            lag_days=lag_days,
        )

        needs_repair = bool(
            lag_days > 1
            or stale_pct >= 5.0
            or missing_market
            or (detailed and completeness_median < settings.sync_completeness_threshold)
        )

        return {
            "as_of": as_of,
            "adjust_type": adjust_type,
            "bar_coverage_pct": coverage_pct,
            "freshness": {
                "market_latest": market_latest,
                "calendar_latest": trade_dates[-1] if trade_dates else None,
                "lag_days": lag_days,
            },
            "stale_codes": stale_codes[:50],
            "gap_summary": {
                "stale_count": stale_total,
                "stale_pct": stale_pct,
                "missing_market_dates": missing_market[:20],
                "completeness_median": completeness_median,
            },
            "repair_plan": repair_plan.to_dict(),
            "needs_repair": needs_repair,
        }
