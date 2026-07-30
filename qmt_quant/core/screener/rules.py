"""Compile screening rules to Polars expressions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import polars as pl
except ImportError:
    pl = None  # type: ignore


def build_filter_expr(conditions: Dict[str, Any]):
    if pl is None:
        return None
    exprs = []
    if conditions.get("exclude_st"):
        exprs.append(~pl.col("name").str.contains("(?i)ST"))
    if conditions.get("max_pe") is not None:
        exprs.append(pl.col("pe").is_not_null() & (pl.col("pe") <= conditions["max_pe"]))
    if conditions.get("min_roe") is not None:
        exprs.append(pl.col("roe").is_not_null() & (pl.col("roe") >= conditions["min_roe"]))
    if conditions.get("ma_bullish"):
        exprs.append(pl.col("ma5") > pl.col("ma20"))
    if not exprs:
        return pl.lit(True)
    out = exprs[0]
    for e in exprs[1:]:
        out = out & e
    return out


def apply_rules(df, conditions: Dict[str, Any], top_n: int = 30):
    if pl is None:
        raise ImportError("polars required in quant-env")
    if not isinstance(df, pl.DataFrame):
        df = pl.from_pandas(df)
    filt = build_filter_expr(conditions)
    if filt is not None:
        df = df.filter(filt)
    sort_col = conditions.get("sort_by", "score")
    if sort_col in df.columns:
        df = df.sort(sort_col, descending=True)
    return df.head(top_n)
