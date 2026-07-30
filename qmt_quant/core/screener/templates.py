"""Screening templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ScreenTemplate:
    id: str
    name: str
    pe_max: float
    roe_min: float
    ma_window: int
    rank_field: str = "momentum_20d"


TEMPLATES: Dict[str, ScreenTemplate] = {
    "low_pe": ScreenTemplate("low_pe", "低估值动量", pe_max=30, roe_min=0.10, ma_window=60),
    "ma_bull": ScreenTemplate("ma_bull", "均线多头", pe_max=100, roe_min=0.05, ma_window=20),
}

TEMPLATE_OPTIONS = [
    {"value": t.id, "label": f"{t.name}（内置模板）"} for t in TEMPLATES.values()
] + [{"value": "custom", "label": "从空白规则新建…"}]
