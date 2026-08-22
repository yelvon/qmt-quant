"""Sync benchmark and Shenwan L1 industry indices into index_daily_bar."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Dict, List, Optional, Sequence, Tuple

from qmt_quant.adapters.qmt.client import XtDataClient, normalize_code, to_qmt_date
from qmt_quant.adapters.qmt.transform import index_bars_from_dataframe
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.sync.indices import (
    BENCHMARK_INDICES,
    benchmark_codes,
    benchmark_name_map,
    filter_industry_codes,
    index_sync_window,
    pick_industry_sector,
)
from qmt_quant.storage.database import db_session
from qmt_quant.storage.index_bars import (
    IndexBarRow,
    index_codes_with_bars,
    list_index_instruments,
    upsert_index_bars,
    upsert_index_instruments,
)

INDEX_BATCH_SIZE = 10
INDEX_BATCH_TIMEOUT_SEC = 90


def _as_str_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def discover_industry_indices(client: XtDataClient) -> Tuple[List[str], Optional[str], Dict[str, str]]:
    try:
        sectors = _as_str_list(client.get_sector_list())
    except Exception:
        return [], None, {}
    sector = pick_industry_sector(sectors)
    if not sector:
        return [], None, {}
    try:
        raw_codes = _as_str_list(client.get_sector_stocks(sector))
    except Exception:
        return [], None, {}
    details: Dict[str, Dict[str, Any]] = {}
    for raw in raw_codes[:80]:
        code = normalize_code(raw)
        try:
            details[code] = client.get_instrument_detail(raw) or {}
        except Exception:
            details[code] = {}
    filtered = filter_industry_codes(raw_codes, details=details)
    names: Dict[str, str] = {}
    for code in filtered:
        detail = details.get(code) or {}
        label = (
            detail.get("InstrumentName")
            or detail.get("instrument_name")
            or detail.get("name")
            or code
        )
        names[code] = str(label)
    return filtered, sector, names


def _load_repair_catalog() -> List[Tuple[str, str, str, Optional[str]]]:
    with db_session() as conn:
        items = list_index_instruments(conn)
    return [
        (str(it["code"]), it.get("name"), str(it.get("kind") or "benchmark"), it.get("source_sector") or None)
        for it in items
        if it.get("code")
    ]


def _fetch_batch(
    client: XtDataClient,
    codes: Sequence[str],
    start: str,
    end: str,
) -> Dict[str, Any]:
    return client.fetch_market_bars(
        list(codes),
        period="1d",
        start_time=to_qmt_date(start),
        end_time=to_qmt_date(end),
        dividend_type="none",
    )


def sync_index_bars(
    *,
    client: Optional[XtDataClient] = None,
    job_start: str,
    job_end: str,
    job_id: Optional[str] = None,
    repair: bool = False,
    lookback_start: Optional[str] = None,
    lookback_end: Optional[str] = None,
) -> Dict[str, Any]:
    if client is None:
        client = XtDataClient()

    industry_source: Optional[str] = None
    failed: List[str] = []
    catalog: List[Tuple[str, Optional[str], str, Optional[str]]] = []
    names = benchmark_name_map()
    for code, name in BENCHMARK_INDICES:
        catalog.append((code, name, "benchmark", None))

    if repair:
        existing = _load_repair_catalog()
        if existing:
            catalog = [
                (c, n, k, s)
                for c, n, k, s in existing
            ]
            industry_source = next((s for _c, _n, k, s in catalog if k == "industry" and s), None)
        else:
            catalog = []
    else:
        industry_codes, industry_source, industry_names = discover_industry_indices(client)
        names.update(industry_names)
        for code in industry_codes:
            catalog.append((code, names.get(code), "industry", industry_source))

    seen = set()
    unique: List[Tuple[str, Optional[str], str, Optional[str]]] = []
    for code, name, kind, source in catalog:
        if code in seen:
            continue
        seen.add(code)
        unique.append((code, name, kind, source))
    catalog = unique

    if catalog:
        with db_session() as conn:
            upsert_index_instruments(conn, catalog)

    codes = [c for c, _n, _k, _s in catalog]
    kind_map = {c: k for c, _n, k, _s in catalog}
    with db_session() as conn:
        has_bars = index_codes_with_bars(conn, codes)

    windows: Dict[Tuple[str, str], List[str]] = {}
    for code in codes:
        start, end = index_sync_window(
            kind=kind_map.get(code, "benchmark"),
            has_rows=code in has_bars,
            job_start=job_start,
            job_end=job_end,
            repair=repair,
            lookback_start=lookback_start,
            lookback_end=lookback_end,
        )
        windows.setdefault((start, end), []).append(code)

    written = 0
    total = len(codes)
    done = 0
    if job_id:
        report_job_progress(
            job_id,
            0.93,
            f"同步基准与行业指数（{total} 只）",
            step="index",
            detail=industry_source or "仅基准",
        )

    for (start, end), group in windows.items():
        for i in range(0, len(group), INDEX_BATCH_SIZE):
            chunk = group[i : i + INDEX_BATCH_SIZE]
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_fetch_batch, client, chunk, start, end)
                    data = future.result(timeout=INDEX_BATCH_TIMEOUT_SEC)
                if not isinstance(data, dict):
                    raise TypeError("invalid_market_bars")
                rows: List[IndexBarRow] = []
                for code in chunk:
                    df = data.get(code)
                    if df is None:
                        df = data.get(normalize_code(code))
                    if df is None:
                        failed.append(code)
                        continue
                    part = index_bars_from_dataframe(code, df)
                    if not part:
                        failed.append(code)
                        continue
                    rows.extend(part)
                if rows:
                    with db_session() as conn:
                        written += upsert_index_bars(conn, rows)
            except FuturesTimeout:
                failed.extend(chunk)
            except Exception:
                failed.extend(chunk)
            done += len(chunk)
            if job_id:
                report_job_progress(
                    job_id,
                    0.93 + 0.04 * (done / max(total, 1)),
                    f"指数 {done}/{total}",
                    step="index",
                )

    return {
        "index_codes": len(codes),
        "index_bars_written": written,
        "index_failed": sorted(set(failed)),
        "industry_source_sector": industry_source,
    }
