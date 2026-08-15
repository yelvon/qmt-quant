"""Date range presets."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Tuple


def resolve_range_preset(preset: str, max_date: str | None = None) -> Tuple[str, str]:
    end = date.fromisoformat(max_date) if max_date else date.today()
    mapping = {
        "1y": 365,
        "3y": 365 * 3,
        "5y": 365 * 5,
        "10y": 365 * 10,
        "20y": 365 * 20,
    }
    if preset == "all":
        start = date(2005, 1, 1)
    else:
        days = mapping.get(preset, mapping["3y"])
        start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


DIVIDEND_MAP = {
    "none": "none",
    "front": "front",
    "back": "back",
}
