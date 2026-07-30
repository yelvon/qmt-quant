"""Research presets for UI and CLI."""

from __future__ import annotations

from typing import Dict, List, Tuple

MA_SHORT_PRESETS: Dict[str, List[int]] = {
    "preset_std": [5, 10, 20],
    "preset_fast": [3, 5, 8],
    "preset_slow": [10, 15, 20],
}

MA_LONG_PRESETS: Dict[str, List[int]] = {
    "preset_std": [30, 60, 120],
    "preset_mid": [20, 40, 60],
    "preset_long": [60, 120, 250],
}

FEE_PRESETS: Dict[str, Dict[str, float]] = {
    "default": {"label": "A股默认", "commission_rate": 0.0003, "stamp_tax_rate": 0.001},
    "low": {"label": "低佣金", "commission_rate": 0.00015, "stamp_tax_rate": 0.001},
    "custom": {"label": "自定义", "commission_rate": 0.0003, "stamp_tax_rate": 0.001},
}

SHORT_MA_PRESETS = {k: {"label": k, "values": v} for k, v in MA_SHORT_PRESETS.items()}
LONG_MA_PRESETS = {k: {"label": k, "values": v} for k, v in MA_LONG_PRESETS.items()}

STRATEGY_OPTIONS = [
    {"value": "ma_cross", "label": "双均线交叉（入门）"},
    {"value": "buy_hold", "label": "买入持有（基准）"},
    {"value": "pe_momentum", "label": "低估值 + 动量"},
]

RANGE_OPTIONS = [
    {"value": "1y", "label": "近 1 年"},
    {"value": "3y", "label": "近 3 年（推荐）"},
    {"value": "5y", "label": "近 5 年"},
    {"value": "all", "label": "全部已有数据"},
]

SECTOR_OPTIONS = [
    {"value": "沪深A股", "label": "沪深 A 股（默认）"},
    {"value": "沪深300", "label": "沪深 300"},
    {"value": "中证500", "label": "中证 500"},
    {"value": "watchlist", "label": "我的自选池"},
]

RANGE_PRESETS = {o["value"]: o for o in RANGE_OPTIONS}


def ma_param_combos(short_preset: str, long_preset: str) -> List[Tuple[int, int]]:
    shorts = MA_SHORT_PRESETS.get(short_preset, MA_SHORT_PRESETS["preset_std"])
    longs = MA_LONG_PRESETS.get(long_preset, MA_LONG_PRESETS["preset_std"])
    return [(s, l) for s in shorts for l in longs if s < l]
