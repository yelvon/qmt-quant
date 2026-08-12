"""Export PostgreSQL bars to Parquet for quant engines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.storage.bars import load_bars_df
from qmt_quant.storage.database import db_session, run_migrations


def export_catalog(*, adjust_type: str = "front", fmt: str = "flat") -> Dict[str, object]:
    """Export bars to flat parquet and/or NautilusTrader ParquetDataCatalog."""
    run_migrations()
    settings = get_settings()
    out: Dict[str, object] = {"format": fmt}

    if fmt in ("flat", "both"):
        catalog_dir = settings.catalog_dir
        catalog_dir.mkdir(parents=True, exist_ok=True)

        with db_session() as conn:
            df = load_bars_df(conn, adjust_type=adjust_type)
        if df.empty:
            out["flat"] = {"exported": 0, "catalog_dir": str(catalog_dir)}
        else:
            exported = 0
            meta: Dict[str, object] = {"adjust_type": adjust_type, "instruments": []}
            for code, group in df.groupby("code"):
                frame = group.sort_values("date").copy()
                path = catalog_dir / f"{code.replace('.', '_')}_{adjust_type}.parquet"
                try:
                    frame.to_parquet(path, index=False)
                except ImportError:
                    path = catalog_dir / f"{code.replace('.', '_')}_{adjust_type}.csv"
                    frame.to_csv(path, index=False)
                exported += 1
                meta["instruments"].append({"code": code, "rows": len(frame), "file": path.name})

            meta_path = catalog_dir / "catalog_meta.json"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            out["flat"] = {"exported": exported, "catalog_dir": str(catalog_dir), "meta": str(meta_path)}

    if fmt in ("nt", "both") or settings.export_nt_catalog:
        from qmt_quant.core.catalog.nt_export import export_nt_catalog

        out["nt"] = export_nt_catalog(adjust_type=adjust_type)

    if fmt == "flat" and "flat" in out:
        return out["flat"]  # type: ignore[return-value]
    return out


def load_price_matrix(
    *,
    adjust_type: str = "front",
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
) -> pd.DataFrame:
    with db_session() as conn:
        df = load_bars_df(
            conn,
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,
        )
    if df.empty:
        return pd.DataFrame()
    pivot = df.pivot(index="date", columns="code", values="close")
    pivot.index = pd.to_datetime(pivot.index)
    return pivot.sort_index()


def load_ohlcv_df(
    *,
    adjust_type: str = "front",
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
) -> pd.DataFrame:
    with db_session() as conn:
        df = load_bars_df(
            conn,
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,
        )
    if df.empty:
        return pd.DataFrame()
    return df.sort_values(["date", "code"])
