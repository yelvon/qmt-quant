"""Delete job records and their derived artifacts (reports, runs, screening rows)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from qmt_quant.config import ROOT_DIR
from qmt_quant.storage.database import DbConnection

_ACTIVE_STATUSES = frozenset({"running", "pending"})


def _collect_artifacts(result: Any, *, paths: Set[str], run_ids: Set[str]) -> None:
    if isinstance(result, dict):
        run_id = result.get("run_id")
        if run_id:
            run_ids.add(str(run_id))
        result_path = result.get("result_path")
        if result_path:
            paths.add(str(result_path))
        for value in result.values():
            _collect_artifacts(value, paths=paths, run_ids=run_ids)
    elif isinstance(result, list):
        for item in result:
            _collect_artifacts(item, paths=paths, run_ids=run_ids)


def _safe_report_path(path_str: str) -> Optional[Path]:
    try:
        path = Path(path_str).resolve()
        reports_root = (ROOT_DIR / "reports").resolve()
        if reports_root in path.parents or path == reports_root:
            return path
    except (OSError, ValueError):
        return None
    return None


def _delete_report_files(paths: Iterable[str]) -> List[str]:
    deleted: List[str] = []
    for raw in paths:
        path = _safe_report_path(raw)
        if path and path.is_file():
            try:
                path.unlink()
                deleted.append(str(path))
            except OSError:
                pass
    return deleted


def _delete_backtest_runs(conn: DbConnection, run_ids: Iterable[str]) -> int:
    count = 0
    for run_id in run_ids:
        row = conn.execute("SELECT result_path FROM backtest_run WHERE id = %s", (run_id,)).fetchone()
        if row and row[0]:
            _delete_report_files([str(row[0])])
        cur = conn.execute("DELETE FROM backtest_run WHERE id = %s", (run_id,))
        count += cur.rowcount
    return count


def _delete_screening_runs(conn: DbConnection, run_ids: Iterable[str]) -> int:
    total = 0
    for run_id in run_ids:
        cur = conn.execute("DELETE FROM screening_result WHERE run_id = %s", (run_id,))
        total += cur.rowcount
    return total


def delete_job_record(conn: DbConnection, job_id: str) -> None:
    conn.execute("DELETE FROM job WHERE id = %s", (job_id,))


def _classify_run_ids(conn: DbConnection, run_ids: Iterable[str]) -> tuple[Set[str], Set[str]]:
    backtest_ids: Set[str] = set()
    screen_ids: Set[str] = set()
    for run_id in run_ids:
        if conn.execute("SELECT 1 FROM backtest_run WHERE id = %s", (run_id,)).fetchone():
            backtest_ids.add(run_id)
        if conn.execute(
            "SELECT 1 FROM screening_result WHERE run_id = %s LIMIT 1",
            (run_id,),
        ).fetchone():
            screen_ids.add(run_id)
    return backtest_ids, screen_ids


def delete_job_artifacts(conn: DbConnection, job: Dict[str, Any]) -> Dict[str, Any]:
    """Remove files/rows derived from a job result. Does not delete market data."""
    result = job.get("result_json") or {}
    paths: Set[str] = set()
    run_ids: Set[str] = set()
    _collect_artifacts(result, paths=paths, run_ids=run_ids)

    backtest_ids, screen_ids = _classify_run_ids(conn, run_ids)
    files_deleted = _delete_report_files(paths)
    screening_rows = _delete_screening_runs(conn, screen_ids) if screen_ids else 0
    backtest_runs = _delete_backtest_runs(conn, backtest_ids) if backtest_ids else 0

    return {
        "files_deleted": len(files_deleted),
        "backtest_runs_deleted": backtest_runs,
        "screening_rows_deleted": screening_rows,
    }


def delete_job(conn: DbConnection, job_id: str) -> Dict[str, Any]:
    from qmt_quant.storage.jobs import get_job

    job = get_job(conn, job_id)
    if not job:
        raise ValueError("not_found")
    status = str(job.get("status") or "")
    if status in _ACTIVE_STATUSES:
        raise ValueError("job_still_active")

    cleanup = delete_job_artifacts(conn, job)
    delete_job_record(conn, job_id)
    return {"job_id": job_id, "deleted": True, **cleanup}


def cleanup_finished_jobs(conn: DbConnection, *, keep_last: int = 30) -> Dict[str, Any]:
    """Delete finished jobs beyond the most recent ``keep_last``, with artifacts."""
    keep_last = max(0, keep_last)
    rows = conn.execute(
        """
        SELECT id FROM job
        WHERE status NOT IN ('running', 'pending')
        ORDER BY created_at DESC
        """
    ).fetchall()
    to_delete = [r[0] for r in rows[keep_last:]]
    summary = {"jobs_deleted": 0, "files_deleted": 0, "backtest_runs_deleted": 0, "screening_rows_deleted": 0}
    for job_id in to_delete:
        out = delete_job(conn, job_id)
        summary["jobs_deleted"] += 1
        summary["files_deleted"] += int(out.get("files_deleted") or 0)
        summary["backtest_runs_deleted"] += int(out.get("backtest_runs_deleted") or 0)
        summary["screening_rows_deleted"] += int(out.get("screening_rows_deleted") or 0)
    return summary
