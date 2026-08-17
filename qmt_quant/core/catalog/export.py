"""Export PostgreSQL bars to Parquet for quant engines."""

from __future__ import annotations

import json
import threading
import time
from typing import Dict, Optional, Sequence

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.core.data.frequency import BarFrequency, bars_to_price_matrix, load_bars
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.storage.bars import list_bar_codes, load_bars_df
from qmt_quant.storage.database import db_session, run_migrations

_PRICE_CACHE_TTL_SECONDS = 30.0
_PRICE_CACHE_MAX_ENTRIES = 16
_price_cache: dict[tuple[object, ...], tuple[float, pd.DataFrame]] = {}
_price_cache_lock = threading.Lock()


def _write_code_frame(frame: pd.DataFrame, path_base, adjust_type: str) -> str:
    path = path_base.parent / f"{path_base.name}_{adjust_type}.parquet"
    try:
        frame.to_parquet(path, index=False)
        return path.name
    except ImportError:
        path = path_base.parent / f"{path_base.name}_{adjust_type}.csv"
        frame.to_csv(path, index=False)
        return path.name


def export_catalog(
    *,
    adjust_type: str = "front",
    fmt: str = "flat",
    codes: Optional[Sequence[str]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, object]:
    """Export bars to flat parquet and/or NautilusTrader ParquetDataCatalog."""
    run_migrations()
    settings = get_settings()
    out: Dict[str, object] = {"format": fmt}

    if fmt in ("flat", "both"):
        catalog_dir = settings.catalog_dir
        catalog_dir.mkdir(parents=True, exist_ok=True)

        with db_session() as conn:
            export_codes = list(codes) if codes else list_bar_codes(conn, adjust_type=adjust_type)

        if not export_codes:
            out["flat"] = {"exported": 0, "catalog_dir": str(catalog_dir)}
        else:
            exported = 0
            meta: Dict[str, object] = {"adjust_type": adjust_type, "instruments": []}
            total = len(export_codes)
            for idx, code in enumerate(export_codes, start=1):
                if job_id and (idx == 1 or idx % 25 == 0 or idx == total):
                    report_job_progress(
                        job_id,
                        0.96 + 0.03 * (idx / max(total, 1)),
                        f"导出验策略文件 {idx}/{total}",
                        step="export",
                        detail=f"当前 {code}",
                    )
                with db_session() as conn:
                    frame = load_bars_df(conn, codes=[code], adjust_type=adjust_type)
                if frame.empty:
                    continue
                frame = frame.sort_values("date")
                path_base = catalog_dir / code.replace(".", "_")
                filename = _write_code_frame(frame, path_base, adjust_type)
                exported += 1
                meta["instruments"].append({"code": code, "rows": len(frame), "file": filename})

            meta_path = catalog_dir / "catalog_meta.json"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            out["flat"] = {"exported": exported, "catalog_dir": str(catalog_dir), "meta": str(meta_path)}

    if fmt in ("nt", "both") or settings.export_nt_catalog:
        from qmt_quant.core.catalog.nt_export import export_nt_catalog

        out["nt"] = export_nt_catalog(adjust_type=adjust_type, codes=codes)

    if fmt == "flat" and "flat" in out:
        return out["flat"]  # type: ignore[return-value]
    return out


def load_price_matrix(
    *,
    adjust_type: str = "front",
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
) -> pd.DataFrame:
    frequency = BarFrequency.parse(bar_frequency)
    key = (
        adjust_type,
        start_date,
        end_date,
        tuple(codes) if codes is not None else None,
        frequency.value,
    )
    now = time.monotonic()
    with _price_cache_lock:
        cached = _price_cache.get(key)
        if cached is not None and now - cached[0] <= _PRICE_CACHE_TTL_SECONDS:
            return cached[1].copy()
    matrix = bars_to_price_matrix(
        load_bars(
            adjust_type=adjust_type,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
            bar_frequency=frequency,
        )
    )
    with _price_cache_lock:
        if len(_price_cache) >= _PRICE_CACHE_MAX_ENTRIES:
            oldest = min(_price_cache, key=lambda item: _price_cache[item][0])
            _price_cache.pop(oldest, None)
        _price_cache[key] = (now, matrix.copy())
    return matrix


def clear_price_matrix_cache() -> None:
    """Invalidate process-local matrix cache after bar mutations or in tests."""
    with _price_cache_lock:
        _price_cache.clear()


def load_ohlcv_df(
    *,
    adjust_type: str = "front",
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
    bar_frequency: BarFrequency | str = BarFrequency.DAILY,
) -> pd.DataFrame:
    return load_bars(
        adjust_type=adjust_type,
        start_date=start_date,
        end_date=end_date,
        codes=codes,
        bar_frequency=bar_frequency,
    )
