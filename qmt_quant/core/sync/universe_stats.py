"""Universe size helpers for coverage / health metrics."""

from __future__ import annotations

from typing import Sequence

from qmt_quant.storage.database import DbConnection
from qmt_quant.storage.instruments import ensure_codes
from qmt_quant.storage.sync_meta import get_meta, set_meta


def universe_meta_key(sector: str) -> str:
    return f"universe_count:{sector}"


def record_universe_count(conn: DbConnection, sector: str, count: int) -> None:
    if count > 0:
        set_meta(conn, universe_meta_key(sector), str(count))


def ensure_instrument_codes(conn: DbConnection, codes: Sequence[str]) -> None:
    ensure_codes(conn, codes)


def resolve_universe_total(
    conn: DbConnection,
    sector: str,
    *,
    bar_codes: int = 0,
) -> tuple[int, bool]:
    cached = get_meta(conn, universe_meta_key(sector))
    if cached and str(cached).isdigit():
        n = int(cached)
        if n > 0:
            return n, False

    inst_count = int(conn.execute("SELECT COUNT(*) FROM instrument").fetchone()[0])
    if inst_count >= 100:
        return inst_count, False

    fallback = max(inst_count, int(bar_codes), 1)
    return fallback, True
