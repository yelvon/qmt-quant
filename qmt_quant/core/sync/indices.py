"""Benchmark and industry index catalogs for QMT bar sync."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from qmt_quant.adapters.qmt.client import normalize_code
from qmt_quant.core.presets import resolve_range_preset

INDUSTRY_CODE_CAP = 40
PREFERRED_INDUSTRY_SECTOR = "迅投一级行业板块指数"

BENCHMARK_INDICES: Tuple[Tuple[str, str], ...] = (
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("000016.SH", "上证50"),
    ("000300.SH", "沪深300"),
    ("000905.SH", "中证500"),
    ("000852.SH", "中证1000"),
)

_SZ_STOCK_PREFIXES = ("000", "001", "002", "003", "300")
_CODE_RE = re.compile(r"^(\d{6})\.(SH|SZ|SI)$", re.IGNORECASE)


def _is_rejected_a_share(code: str) -> bool:
    raw = (code or "").strip().upper()
    if "." not in raw:
        raw = normalize_code(raw)
    match = _CODE_RE.match(raw)
    if not match:
        return False
    digits, market = match.group(1), match.group(2).upper()
    if market == "SH":
        return digits.startswith("6") or digits.startswith("5")
    if market == "SZ":
        return digits.startswith(_SZ_STOCK_PREFIXES)
    return False


def benchmark_codes() -> List[str]:
    return [code for code, _name in BENCHMARK_INDICES]


def benchmark_name_map() -> Dict[str, str]:
    return {code: name for code, name in BENCHMARK_INDICES}


def looks_like_index_code(code: str) -> bool:
    """Reject A-share stocks that must never land in index_daily_bar."""
    raw = (code or "").strip().upper()
    if not raw:
        return False
    if "." not in raw:
        raw = normalize_code(raw)
    if raw.endswith(".SI"):
        return True
    match = _CODE_RE.match(raw)
    if not match:
        return False
    digits, market = match.group(1), match.group(2).upper()
    if market == "SH":
        if digits.startswith("6") or digits.startswith("5"):
            return False
        return digits.startswith("00") or digits.startswith("880")
    if market == "SZ":
        return digits.startswith("399")
    return False


def is_industry_index(code: str, name: str | None = None) -> bool:
    if _is_rejected_a_share(code):
        return False
    if looks_like_index_code(code):
        return True
    label = str(name or "").strip().upper()
    return label.startswith("SW")


def pick_industry_sector(sectors: Sequence[str]) -> Optional[str]:
    names = [str(s).strip() for s in sectors if str(s).strip()]
    if PREFERRED_INDUSTRY_SECTOR in names:
        return PREFERRED_INDUSTRY_SECTOR
    ranked = [
        name
        for name in names
        if "一级行业" in name and "指数" in name and "二级" not in name and "三级" not in name
    ]
    if not ranked:
        ranked = [name for name in names if "申万一级" in name and "指数" in name]
    return ranked[0] if ranked else None


def filter_industry_codes(
    codes: Iterable[str],
    *,
    details: Optional[Dict[str, Dict[str, Any]]] = None,
    cap: int = INDUSTRY_CODE_CAP,
) -> List[str]:
    details = details or {}
    out: List[str] = []
    seen = set()
    for raw in codes:
        code = normalize_code(str(raw))
        if code in seen:
            continue
        detail = details.get(code) or details.get(raw) or {}
        name = (
            detail.get("InstrumentName")
            or detail.get("instrument_name")
            or detail.get("name")
        )
        if not is_industry_index(code, name if isinstance(name, str) else None):
            continue
        seen.add(code)
        out.append(code)
        if len(out) >= cap:
            break
    return out


def index_sync_window(
    *,
    kind: str,
    has_rows: bool,
    job_start: str,
    job_end: str,
    repair: bool = False,
    lookback_start: Optional[str] = None,
    lookback_end: Optional[str] = None,
    force_full_windows: bool = False,
) -> Tuple[str, str]:
    if repair:
        start = lookback_start or job_start
        end = lookback_end or job_end
        return start, end
    if has_rows and not force_full_windows:
        return job_start, job_end
    if kind == "benchmark":
        return resolve_range_preset("20y", max_date=job_end)
    cap_start, cap_end = resolve_range_preset("3y", max_date=job_end)
    start = max(job_start or cap_start, cap_start)
    end = min(job_end or cap_end, cap_end)
    if start > end:
        return cap_start, cap_end
    return start, end
