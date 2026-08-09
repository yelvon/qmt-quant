"""Universe size helpers for coverage / health metrics."""

from __future__ import annotations

import sqlite3
from typing import Sequence

from qmt_quant.storage.sync_meta import get_meta, set_meta


def universe_meta_key(sector: str) -> str:
    return f"universe_count:{sector}"


def record_universe_count(conn: sqlite3.Connection, sector: str, count: int) -> None:
    if count > 0:
        set_meta(conn, universe_meta_key(sector), str(count))


def ensure_instrument_codes(conn: sqlite3.Connection, codes: Sequence[str]) -> None:
    """Ensure instrument rows exist for universe members (name filled later)."""
    if not codes:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO instrument(code) VALUES (?)",
        [(c,) for c in codes],
    )


def resolve_universe_total(
    conn: sqlite3.Connection,
    sector: str,
    *,
    bar_codes: int = 0,
) -> tuple[int, bool]:
    """Return (universe_total, is_estimated)."""
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
