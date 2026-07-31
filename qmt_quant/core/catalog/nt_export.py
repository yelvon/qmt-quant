"""Export SQLite bars to NautilusTrader ParquetDataCatalog."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.storage.bars import load_bars_df
from qmt_quant.storage.database import db_session, run_migrations

VENUE = "CN_A_SHARE"
MAX_INSTRUMENTS = 10


def export_nt_catalog(
    *,
    adjust_type: str = "front",
    codes: Optional[Sequence[str]] = None,
    limit: int = MAX_INSTRUMENTS,
) -> Dict[str, object]:
    run_migrations()
    settings = get_settings()
    catalog_path = settings.catalog_nt_path
    catalog_path.mkdir(parents=True, exist_ok=True)

    try:
        from nautilus_trader.model.data import Bar, BarSpecification, BarType
        from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
        from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
        from nautilus_trader.model.instruments import Equity
        from nautilus_trader.model.objects import Currency, Price, Quantity
        from nautilus_trader.persistence.catalog import ParquetDataCatalog
    except ImportError as exc:
        return {"error": "nautilus_trader_not_installed", "message": str(exc)}

    with db_session() as conn:
        df = load_bars_df(conn, adjust_type=adjust_type, codes=codes)

    if df.empty:
        return {"exported": 0, "catalog_dir": str(catalog_path)}

    catalog = ParquetDataCatalog(str(catalog_path))
    exported = 0
    bar_count = 0
    venue = Venue(VENUE)

    for code, group in df.groupby("code"):
        if exported >= limit:
            break
        frame = group.sort_values("date")
        symbol = Symbol(code.split(".")[0])
        instrument_id = InstrumentId(symbol=symbol, venue=venue)
        currency = Currency.from_str("CNY")
        instrument = Equity(
            instrument_id=instrument_id,
            raw_symbol=symbol,
            currency=currency,
            price_precision=2,
            price_increment=Price.from_str("0.01"),
            lot_size=Quantity.from_int(100),
            ts_event=0,
            ts_init=0,
        )
        spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
        bar_type = BarType(instrument_id, spec, AggregationSource.EXTERNAL)

        bars: List[Bar] = []
        for _, row in frame.iterrows():
            ts = pd.Timestamp(row["date"]).tz_localize("Asia/Shanghai")
            ts_ns = int(ts.timestamp() * 1_000_000_000)
            bars.append(
                Bar(
                    bar_type=bar_type,
                    open=Price.from_str(f"{float(row['open']):.2f}"),
                    high=Price.from_str(f"{float(row['high']):.2f}"),
                    low=Price.from_str(f"{float(row['low']):.2f}"),
                    close=Price.from_str(f"{float(row['close']):.2f}"),
                    volume=Quantity.from_str(str(int(float(row.get('volume') or 0)))),
                    ts_event=ts_ns,
                    ts_init=ts_ns,
                )
            )
        if not bars:
            continue
        catalog.write_data([instrument])
        catalog.write_data(bars)
        exported += 1
        bar_count += len(bars)

    return {
        "exported": exported,
        "bars": bar_count,
        "catalog_dir": str(catalog_path),
        "venue": VENUE,
    }
