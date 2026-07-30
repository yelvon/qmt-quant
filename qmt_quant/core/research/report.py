"""Research report helpers."""

from __future__ import annotations

from typing import Any, Dict, List


def summarize_combos(combos: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    sorted_rows = sorted(combos, key=lambda r: r.get("total_return_pct", 0), reverse=True)
    return sorted_rows[:top_n]


def heatmap_payload(combos: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "categories": [c.get("label", "") for c in combos],
        "values": [c.get("total_return_pct", 0) for c in combos],
    }
