"""Screening rule DSL parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from qmt_quant.core.screener.templates import TEMPLATES


@dataclass
class ScreeningRule:
    name: str = ""
    as_of: Optional[str] = None
    pe_max: Optional[float] = None
    roe_min: Optional[float] = None
    ma_window: int = 60
    ma_bullish: bool = False
    exclude_st: Optional[bool] = True
    list_days_lt: Optional[int] = 120
    rank_by: str = "score"
    top_n: int = 30
    filters: List[Dict[str, Any]] = field(default_factory=list)


def load_rule(path: str | Path) -> ScreeningRule:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return parse_rule(raw)


def parse_rule(raw: Dict[str, Any]) -> ScreeningRule:
    rule = ScreeningRule(name=raw.get("name", ""))
    rule.as_of = raw.get("as_of")
    if rule.as_of == "latest_trading_day":
        rule.as_of = None
    exclude = raw.get("exclude") or []
    for item in exclude:
        if isinstance(item, dict):
            if item.get("st"):
                rule.exclude_st = True
            if "list_days_lt" in item:
                rule.list_days_lt = int(item["list_days_lt"])
    rule.rank_by = raw.get("rank_by", "score")
    rule.top_n = int(raw.get("top_n", 30))
    rule.filters = list(raw.get("filters") or [])
    for f in rule.filters:
        field_name = f.get("field", "")
        op = f.get("op", "")
        value = f.get("value")
        if field_name == "pe_ttm" and op == "<":
            rule.pe_max = float(value)
        elif field_name == "roe" and op == ">":
            rule.roe_min = float(value)
        elif field_name == "close" and op == "above_ma":
            rule.ma_bullish = True
            params = f.get("params") or {}
            rule.ma_window = int(params.get("window", 60))
    return rule


def rule_from_template(template_id: str) -> ScreeningRule:
    t = TEMPLATES.get(template_id, TEMPLATES["low_pe"])
    return ScreeningRule(
        name=t.name,
        pe_max=t.pe_max,
        roe_min=t.roe_min,
        ma_window=t.ma_window,
        ma_bullish=template_id in ("ma_bull", "ma_bullish"),
        rank_by=t.rank_field,
    )
