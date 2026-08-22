"""Transform xtquant data to storage rows."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from qmt_quant.adapters.qmt.client import normalize_code
from qmt_quant.storage.bars import BarRow
from qmt_quant.storage.index_bars import IndexBarRow


def bars_from_dataframe(
    code: str,
    df: pd.DataFrame,
    adjust_type: str = "front",
) -> List[BarRow]:
    if df is None or df.empty:
        return []
    frame = df.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    rows: List[BarRow] = []
    for ts, row in frame.iterrows():
        o = _num(row.get("open"))
        h = _num(row.get("high"))
        l = _num(row.get("low"))
        close = _num(row.get("close"))
        volume = _num(row.get("volume"))
        quality = _bar_quality(o, h, l, close, volume)
        rows.append(
            BarRow(
                code=normalize_code(code),
                date=pd.Timestamp(ts).strftime("%Y-%m-%d"),
                adjust_type=adjust_type,
                open=o,
                high=h,
                low=l,
                close=close,
                volume=volume,
                amount=_num(row.get("amount")),
                pre_close=_num(row.get("pre_close") or row.get("preclose")),
                quality_status=quality,
            )
        )
    return rows


def index_bars_from_dataframe(code: str, df: pd.DataFrame) -> List[IndexBarRow]:
    rows: List[IndexBarRow] = []
    for bar in bars_from_dataframe(code, df, adjust_type="none"):
        rows.append(
            IndexBarRow(
                code=bar.code,
                date=bar.date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                amount=bar.amount,
                pre_close=bar.pre_close,
                turnover=None,
                quality_status=bar.quality_status,
            )
        )
    return rows


def _bar_quality(
    open_: Optional[float],
    high: Optional[float],
    low: Optional[float],
    close: Optional[float],
    volume: Optional[float],
) -> str:
    if close is None or close <= 0:
        return "bad"
    if high is not None and low is not None and high < low:
        return "bad"
    if open_ is not None and high is not None and low is not None:
        if open_ > high or open_ < low or close > high or close < low:
            return "bad"
    if volume is None or volume <= 0:
        return "suspicious"
    return "ok"


def financial_rows_from_frame(
    code: str,
    table: str,
    df: pd.DataFrame,
) -> List[Tuple[str, str, Optional[str], Dict[str, Any]]]:
    if df is None or df.empty:
        return []
    rows: List[Tuple[str, str, Optional[str], Dict[str, Any]]] = []
    for _, row in df.iterrows():
        report_date = _date_str(row, ["report_date", "m_timetag", "endDate"])
        announce_date = _date_str(row, ["announce_date", "announceDate", "m_anntime"])
        payload = {k: _serialize(v) for k, v in row.to_dict().items()}
        if report_date:
            rows.append((normalize_code(code), report_date, announce_date, payload))
    return rows


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _date_str(row: pd.Series, candidates: Iterable[str]) -> Optional[str]:
    for key in candidates:
        if key in row and row[key] is not None and not pd.isna(row[key]):
            return pd.Timestamp(row[key]).strftime("%Y-%m-%d")
    return None


def _serialize(v: Any) -> Any:
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if pd.isna(v):
        return None
    return v
