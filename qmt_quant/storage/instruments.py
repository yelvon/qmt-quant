"""Instrument registry — ``instrument`` table as code/name cache (QMT fetched once)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from qmt_quant.adapters.qmt.client import XtDataClient
from qmt_quant.storage.database import DbConnection

# SQL fragment: name not yet populated from QMT
NAME_MISSING_SQL = (
    "(name IS NULL OR btrim(name) = '' OR name = code OR name = split_part(code, '.', 1))"
)


def name_is_missing(code: str, name: Optional[str]) -> bool:
    if name is None:
        return True
    text = str(name).strip()
    if not text:
        return True
    base = code.split(".")[0]
    return text == code or text == base


def ensure_codes(conn: DbConnection, codes: Sequence[str]) -> int:
    """Ensure instrument rows exist (code only). Never overwrites names."""
    if not codes:
        return 0
    unique = list(dict.fromkeys(codes))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO instrument(code) VALUES (%s) ON CONFLICT(code) DO NOTHING",
            [(c,) for c in unique],
        )
        return cur.rowcount


def get_name_map(conn: DbConnection, codes: Sequence[str]) -> Dict[str, Optional[str]]:
    """Read cached names from DB only — no QMT calls."""
    if not codes:
        return {}
    rows = conn.execute(
        "SELECT code, name FROM instrument WHERE code = ANY(%s)",
        (list(codes),),
    ).fetchall()
    return {str(code): name for code, name in rows}


def list_missing_name_codes(
    conn: DbConnection,
    codes: Optional[Sequence[str]] = None,
    *,
    limit: Optional[int] = None,
) -> List[str]:
    """Return codes whose names are not yet cached."""
    params: List[Any] = []
    if codes:
        unique = list(dict.fromkeys(codes))
        if not unique:
            return []
        placeholders = ",".join(["%s"] * len(unique))
        sql = f"""
            SELECT code FROM instrument
            WHERE code IN ({placeholders}) AND {NAME_MISSING_SQL}
            ORDER BY code
        """
        params.extend(unique)
    else:
        sql = f"""
            SELECT i.code FROM instrument i
            WHERE {NAME_MISSING_SQL}
              AND EXISTS (SELECT 1 FROM daily_bar b WHERE b.code = i.code LIMIT 1)
            ORDER BY i.code
        """
    if limit is not None and limit > 0:
        sql += " LIMIT %s"
        params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [str(r[0]) for r in rows]


def count_missing_names(conn: DbConnection, codes: Optional[Sequence[str]] = None) -> int:
    if codes:
        unique = list(dict.fromkeys(codes))
        if not unique:
            return 0
        placeholders = ",".join(["%s"] * len(unique))
        row = conn.execute(
            f"SELECT COUNT(*) FROM instrument WHERE code IN ({placeholders}) AND {NAME_MISSING_SQL}",
            tuple(unique),
        ).fetchone()
    else:
        row = conn.execute(
            f"""
            SELECT COUNT(*) FROM instrument i
            WHERE {NAME_MISSING_SQL}
              AND EXISTS (SELECT 1 FROM daily_bar b WHERE b.code = i.code LIMIT 1)
            """
        ).fetchone()
    return int(row[0] if row else 0)


def _profile_from_detail(code: str, detail: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str], bool]:
    name = detail.get("InstrumentName") or detail.get("name") or ""
    name = str(name).strip()
    if name_is_missing(code, name):
        name = ""
    list_date = detail.get("OpenDate") or detail.get("list_date")
    delist_date = detail.get("ExpireDate") or detail.get("delist_date")
    is_st = "ST" in name.upper() if name else bool(detail.get("IsST") or detail.get("is_st"))
    return (
        name,
        str(list_date)[:10] if list_date else None,
        str(delist_date)[:10] if delist_date else None,
        is_st,
    )


def upsert_profile(
    conn: DbConnection,
    code: str,
    *,
    name: str,
    list_date: Optional[str] = None,
    delist_date: Optional[str] = None,
    is_st: Optional[bool] = None,
) -> None:
    if name_is_missing(code, name):
        return
    conn.execute(
        """
        INSERT INTO instrument(code, name, list_date, delist_date, is_st, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT(code) DO UPDATE SET
            name = EXCLUDED.name,
            list_date = COALESCE(EXCLUDED.list_date, instrument.list_date),
            delist_date = COALESCE(EXCLUDED.delist_date, instrument.delist_date),
            is_st = COALESCE(EXCLUDED.is_st, instrument.is_st),
            updated_at = NOW()
        """,
        (code, name, list_date, delist_date, is_st),
    )


def fetch_and_store_names(
    conn: DbConnection,
    codes: Sequence[str],
    *,
    client: Optional[XtDataClient] = None,
    job_id: Optional[str] = None,
    batch_size: int = 50,
    limit: Optional[int] = None,
) -> int:
    """Fetch names from QMT only for codes missing in ``instrument``; persist to DB."""
    if not codes:
        return 0

    ensure_codes(conn, codes)
    missing = list_missing_name_codes(conn, codes, limit=limit)
    if not missing:
        return 0

    if client is None:
        client = XtDataClient()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    from qmt_quant.config import get_settings
    from qmt_quant.core.jobs.context import is_job_cancelled, report_job_progress
    from qmt_quant.core.sync.parallel import qmt_semaphore

    settings = get_settings()
    workers = max(1, min(int(settings.sync_concurrency), 4))
    updated = 0
    total = len(missing)
    size = max(1, batch_size)

    def _fetch_one(code: str) -> Optional[Tuple[str, str, Optional[str], Optional[str], bool]]:
        try:
            with qmt_semaphore():
                detail = client.get_instrument_detail(code)
        except Exception:
            return None
        name, list_date, delist_date, is_st = _profile_from_detail(code, detail or {})
        if not name:
            return None
        return code, name, list_date, delist_date, is_st

    for offset in range(0, total, size):
        if job_id and is_job_cancelled(job_id):
            break
        batch = missing[offset : offset + size]
        if job_id:
            done = min(offset + len(batch), total)
            report_job_progress(
                job_id,
                0.91 + 0.07 * (done / max(total, 1)),
                f"补全股票名称 {done}/{total}",
                step="names",
                detail=f"本批 {len(batch)} 只",
            )

        if workers == 1:
            profiles = [_fetch_one(code) for code in batch]
        else:
            profiles = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_fetch_one, code): code for code in batch}
                for future in as_completed(futures):
                    if job_id and is_job_cancelled(job_id):
                        break
                    row = future.result()
                    if row:
                        profiles.append(row)

        for row in profiles:
            if not row:
                continue
            code, name, list_date, delist_date, is_st = row
            upsert_profile(
                conn,
                code,
                name=name,
                list_date=list_date,
                delist_date=delist_date,
                is_st=is_st,
            )
            updated += 1

        if job_id and is_job_cancelled(job_id):
            break

    return updated


def backfill_names_after_sync(
    conn: DbConnection,
    codes: Sequence[str],
    *,
    client: Optional[XtDataClient] = None,
    job_id: Optional[str] = None,
    batch_size: int = 50,
) -> int:
    """After bar sync: fill names for synced universe codes still missing in cache."""
    return fetch_and_store_names(
        conn,
        codes,
        client=client,
        job_id=job_id,
        batch_size=batch_size,
    )


def backfill_missing_names(
    conn: DbConnection,
    *,
    client: Optional[XtDataClient] = None,
    limit: int = 300,
    sector_codes: Optional[Sequence[str]] = None,
) -> int:
    """Manual/API: fetch up to ``limit`` missing names (optionally scoped to a universe)."""
    cap = max(1, min(int(limit), 500))
    if sector_codes is not None:
        ensure_codes(conn, sector_codes)
        return fetch_and_store_names(
            conn,
            sector_codes,
            client=client,
            batch_size=50,
            limit=cap,
        )
    missing = list_missing_name_codes(conn, limit=cap)
    if not missing:
        return 0
    return fetch_and_store_names(
        conn,
        missing,
        client=client,
        batch_size=50,
    )
