"""Parquet catalog helpers for validation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.core.catalog.export import load_price_matrix


BAR_TYPE = "CN_A_SHARE-1-DAY-LAST-EXTERNAL"


def catalog_dir() -> Path:
    return get_settings().catalog_dir


def load_bars(
    *,
    codes: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    return load_price_matrix(
        adjust_type=get_settings().bar_adjust_type,
        start_date=start_date,
        end_date=end_date,
        codes=codes,
    )


def catalog_exists() -> bool:
    d = catalog_dir()
    return d.exists() and any(d.glob("*.parquet"))
