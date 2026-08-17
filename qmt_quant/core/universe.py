"""Point-in-time instrument universe shared by research, validation and screening."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import pandas as pd

from qmt_quant.storage.database import DbConnection, db_session


@dataclass(frozen=True)
class PointInTimeUniverse:
    """Filter instruments by listing life cycle as known for a requested date."""

    conn: DbConnection

    def filter(self, codes: Iterable[str], as_of: Optional[str]) -> List[str]:
        ordered = sorted(dict.fromkeys(str(code) for code in codes if code))
        if not ordered or not as_of:
            return ordered
        rows = self.conn.execute(
            """
            SELECT code
            FROM instrument
            WHERE code = ANY(%s)
              AND (list_date IS NULL OR list_date = '' OR list_date <= %s)
              AND (delist_date IS NULL OR delist_date = '' OR delist_date >= %s)
            """,
            (ordered, as_of, as_of),
        ).fetchall()
        eligible = {str(row[0]) for row in rows}
        # Codes absent from instrument remain usable: missing metadata must not silently
        # turn a valid explicit pool into an empty one.
        known_rows = self.conn.execute(
            "SELECT code FROM instrument WHERE code = ANY(%s)",
            (ordered,),
        ).fetchall()
        known = {str(row[0]) for row in known_rows}
        return [code for code in ordered if code not in known or code in eligible]


def filter_universe_as_of(codes: Iterable[str], as_of: Optional[str]) -> List[str]:
    """Convenience entry point for all strategy layers."""
    with db_session() as conn:
        return PointInTimeUniverse(conn).filter(codes, as_of)


def mask_prices_by_lifecycle(prices: pd.DataFrame) -> pd.DataFrame:
    """Mask every bar outside the instrument's listing lifecycle."""
    if prices.empty:
        return prices
    masked = prices.copy()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT code, list_date, delist_date FROM instrument WHERE code = ANY(%s)",
            (list(map(str, masked.columns)),),
        ).fetchall()
    for code, listed, delisted in rows:
        if code not in masked:
            continue
        if listed:
            masked.loc[masked.index < pd.Timestamp(str(listed)[:10]), code] = pd.NA
        if delisted:
            masked.loc[masked.index > pd.Timestamp(str(delisted)[:10]), code] = pd.NA
    return masked
