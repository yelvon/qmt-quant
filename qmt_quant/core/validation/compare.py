"""Compare VectorBT research vs validation results."""

from __future__ import annotations

from typing import Any, Dict, Optional


def compare_with_research(
    validation_return_pct: float,
    research_metrics: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not research_metrics:
        return {
            "research_return_pct": None,
            "delta_pct": None,
            "verdict": "可以采用" if validation_return_pct > 0 else "建议复核",
        }
    research_return = float(research_metrics.get("total_return_pct", 0))
    delta = round(validation_return_pct - research_return, 2)
    verdict = "可以采用"
    if abs(delta) > 10:
        verdict = "建议复核"
    if validation_return_pct < 0:
        verdict = "不建议"
    return {
        "research_return_pct": research_return,
        "validation_return_pct": validation_return_pct,
        "delta_pct": delta,
        "verdict": verdict,
    }
