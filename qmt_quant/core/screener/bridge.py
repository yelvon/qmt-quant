"""Bridge screening results to research/validation universe."""

from __future__ import annotations

import json
from typing import List

from qmt_quant.storage.database import db_session


def load_codes_from_screening(screening_id: int) -> List[str]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT run_id FROM screening_result WHERE id=?",
            (screening_id,),
        ).fetchone()
        if not row:
            return []
        run_id = row[0]
        rows = conn.execute(
            "SELECT code FROM screening_result WHERE run_id=? ORDER BY rank_no",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def load_codes_by_run_id(run_id: str) -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT code FROM screening_result WHERE run_id=? ORDER BY rank_no",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def universe_arg(codes: List[str]) -> str:
    return ",".join(codes)
