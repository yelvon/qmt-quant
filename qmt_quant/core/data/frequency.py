"""Bar frequency normalization, loading, and daily-to-weekly aggregation."""

from __future__ import annotations

from enum import Enum
from typing import Sequence

import pandas as pd


class BarFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"

    @classmethod
    def parse(cls, value: "BarFrequency | str | None") -> "BarFrequency":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value or cls.DAILY.value).lower())
        except ValueError as exc:
            raise ValueError(f"unsupported bar_frequency: {value}") from exc


def aggregate_daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily OHLCV by code and calendar week.

    The output date is each instrument's actual last trading date in that week,
    so holiday-shortened weeks do not invent a Friday bar. ``pre_close`` is the
    first daily bar's prior close, while volume and amount are summed.
    """
    if daily.empty:
        return daily.copy()
    required = {"date", "code", "open", "high", "low", "close"}
    missing = required.difference(daily.columns)
    if missing:
        raise ValueError(f"daily bars missing columns: {sorted(missing)}")

    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["code", "date"])
    frame["_week"] = frame["date"].dt.to_period("W-FRI")
    aggregations: dict[str, str] = {
        "date": "last",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    }
    for column, method in (
        ("volume", "sum"),
        ("amount", "sum"),
        ("pre_close", "first"),
    ):
        if column in frame.columns:
            aggregations[column] = method
    for column in frame.columns:
        if column not in {*aggregations, "code", "_week"}:
            aggregations[column] = "last"
    weekly = (
        frame.groupby(["code", "_week"], sort=True, observed=True)
        .agg(aggregations)
        .reset_index(drop=False)
        .drop(columns="_week")
    )
    return weekly.sort_values(["date", "code"]).reset_index(drop=True)


def bars_to_price_matrix(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()
    pivot = bars.pivot(index="date", columns="code", values="close")
    pivot.index = pd.to_datetime(pivot.index)
    return pivot.sort_index()


def apply_bar_frequency(
    daily: pd.DataFrame,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
) -> pd.DataFrame:
    frequency = BarFrequency.parse(bar_frequency)
    if frequency is BarFrequency.WEEKLY:
        return aggregate_daily_to_weekly(daily)
    return daily.sort_values(["date", "code"]).reset_index(drop=True)


def load_bars(
    *,
    adjust_type: str = "front",
    start_date: str | None = None,
    end_date: str | None = None,
    codes: Sequence[str] | None = None,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
) -> pd.DataFrame:
    """Unified loader. Always reads locally stored daily bars."""
    from qmt_quant.storage.bars import load_bars_df
    from qmt_quant.storage.database import db_session

    with db_session() as conn:
        daily = load_bars_df(
            conn,
            codes=list(codes) if codes is not None else None,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,
        )
    return apply_bar_frequency(daily, bar_frequency)
