"""Financial factor alignment for research."""

from __future__ import annotations

import json
from typing import Dict

import pandas as pd

from qmt_quant.storage.database import DbConnection


def load_pe_matrix(conn: DbConnection, dates: pd.DatetimeIndex, codes: list[str]) -> pd.DataFrame:
    matrix = pd.DataFrame(index=dates, columns=codes, dtype=float)
    for code in codes:
        rows = conn.execute(
            """
            SELECT announce_date, data_json FROM financial_pershareindex
            WHERE code = %s AND announce_date IS NOT NULL
            ORDER BY announce_date
            """,
            (code,),
        ).fetchall()
        if not rows:
            continue
        series = []
        for announce_date, payload in rows:
            data = json.loads(payload)
            pe = data.get("pe_ttm") or data.get("s_fa_pe") or data.get("PE")
            if pe is not None:
                series.append((pd.Timestamp(announce_date), float(pe)))
        if not series:
            continue
        s = pd.Series({d: v for d, v in series}).sort_index()
        aligned = s.reindex(dates, method="ffill")
        matrix[code] = aligned.values
    return matrix
