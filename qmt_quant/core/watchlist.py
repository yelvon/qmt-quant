"""Watchlist file read/write for web UI and backtest universe."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from qmt_quant.adapters.qmt.client import normalize_code
from qmt_quant.config import get_settings

MAX_WATCHLIST_SIZE = 200
WATCHLIST_HEADER = "# 自选池，一行一个代码"
_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ)$")

def read_watchlist_codes(path: Path | None = None) -> List[str]:
    settings = get_settings()
    p = path or settings.resolve_path(settings.watchlist_path)
    if not p.exists():
        return []
    codes: List[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            code = normalize_code(line)
            if _CODE_RE.match(code):
                codes.append(code)
    return codes


def _fetch_instrument_names(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    try:
        from qmt_quant.storage.database import db_session
        from qmt_quant.storage.instruments import get_name_map

        with db_session() as conn:
            names = get_name_map(conn, codes)
        return {code: str(name or "") for code, name in names.items()}
    except Exception:
        return {}


def normalize_watchlist_codes(raw_codes: List[str]) -> List[str]:
    """Normalize, dedupe (preserve order), and cap watchlist codes."""
    out: List[str] = []
    seen: set[str] = set()
    for raw in raw_codes:
        text = str(raw or "").strip()
        if not text or text.startswith("#"):
            continue
        code = normalize_code(text)
        if not _CODE_RE.match(code):
            raise ValueError(f"无法识别股票代码：{text}，请从搜索结果中选择或使用六位代码")
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    if len(out) > MAX_WATCHLIST_SIZE:
        raise ValueError(f"自选池最多 {MAX_WATCHLIST_SIZE} 只")
    return out


def list_watchlist_items() -> List[Dict[str, str]]:
    codes = read_watchlist_codes()
    names = _fetch_instrument_names(codes)
    return [{"code": code, "name": names.get(code, "")} for code in codes]


def save_watchlist(raw_codes: List[str]) -> List[str]:
    codes = normalize_watchlist_codes(raw_codes)
    settings = get_settings()
    path = settings.resolve_path(settings.watchlist_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = WATCHLIST_HEADER + "\n" + "\n".join(codes)
    if codes:
        content += "\n"
    path.write_text(content, encoding="utf-8")
    return codes


def watchlist_path_display() -> str:
    settings = get_settings()
    return str(settings.resolve_path(settings.watchlist_path))
