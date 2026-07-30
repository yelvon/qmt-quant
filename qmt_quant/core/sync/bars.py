"""Daily bar sync."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from qmt_quant.adapters.qmt.client import XtDataClient, to_qmt_date
from qmt_quant.adapters.qmt.transform import bars_from_dataframe
from qmt_quant.config import get_settings
from qmt_quant.core.presets import DIVIDEND_MAP, resolve_range_preset
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.bars import upsert_bars
from qmt_quant.storage.database import db_session, run_migrations


def sync_bars(
    *,
    sector: str = "沪深A股",
    start_date: Optional[str] = None,
    adjust_type: str = "front",
    incremental: bool = False,
    incremental_days: int = 5,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    codes = resolve_universe(sector)
    client = XtDataClient()

    if incremental:
        start, end = (date.today() - timedelta(days=incremental_days)).isoformat(), date.today().isoformat()
    elif start_date:
        start, end = start_date, date.today().isoformat()
    else:
        start, end = resolve_range_preset("5y")

    dividend = DIVIDEND_MAP.get(adjust_type, "front")
    download_stats = client.download_history(
        codes,
        period="1d",
        start_time=to_qmt_date(start),
        end_time=to_qmt_date(end),
    )

    written = 0
    with db_session() as conn:
        batch_size = settings.sync_batch_size
        for i in range(0, len(codes), batch_size):
            chunk = codes[i : i + batch_size]
            data = client.get_market_bars(
                chunk,
                period="1d",
                start_time=to_qmt_date(start),
                end_time=to_qmt_date(end),
                dividend_type=dividend,
            )
            for code, df in data.items():
                rows = bars_from_dataframe(code, df, adjust_type=adjust_type)
                written += upsert_bars(conn, rows)

    result = {
        "sector": sector,
        "codes": len(codes),
        "start": start,
        "end": end,
        "adjust_type": adjust_type,
        "download_success": download_stats.success,
        "download_failed": download_stats.failed,
        "failed_codes": download_stats.failed_codes,
        "bars_written": written,
    }

    if settings.auto_export_catalog:
        from qmt_quant.core.catalog.export import export_catalog

        result["catalog"] = export_catalog(adjust_type=adjust_type)
    return result
