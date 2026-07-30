"""Load price matrices for research."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.config import get_settings


def load_research_prices(
    *,
    codes: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    settings = get_settings()
    return load_price_matrix(
        adjust_type=settings.bar_adjust_type,
        start_date=start_date,
        end_date=end_date,
        codes=codes,
    )
