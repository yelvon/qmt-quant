"""Bridge screening results to research/validation universe."""

from __future__ import annotations

from typing import List, Optional

from qmt_quant.storage.database import db_session


def load_codes_from_screening(screening_id: int) -> List[str]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT run_id FROM screening_result WHERE id=%s",
            (screening_id,),
        ).fetchone()
        if not row:
            return []
        run_id = row[0]
        rows = conn.execute(
            "SELECT code FROM screening_result WHERE run_id=%s ORDER BY rank_no",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def load_codes_by_run_id(run_id: str) -> List[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT code FROM screening_result WHERE run_id=%s ORDER BY rank_no",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows]


def load_latest_screening_run() -> Optional[str]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT run_id FROM screening_result ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def universe_arg(codes: List[str]) -> str:
    return ",".join(codes)


def run_screen_backtest(
    *,
    run_id: str,
    engine: str = "vectorbt",
    range_preset: str = "3y",
) -> dict:
    codes = load_codes_by_run_id(run_id)
    if not codes:
        return {"error": "no_screen_results", "run_id": run_id}
    if engine in ("vectorbt", "research"):
        from qmt_quant.core.research.runner import run_research

        return run_research(
            strategy_id="screening_rebalance",
            range_preset=range_preset,
            codes=codes,
            screen_run_id=run_id,
        )
    from qmt_quant.core.validation.runner import run_validation

    return run_validation(
        strategy_id="screening_rebalance",
        range_preset=range_preset,
        screen_run_id=run_id,
        codes=codes,
    )
