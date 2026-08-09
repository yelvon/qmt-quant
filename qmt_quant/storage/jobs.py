"""Job and backtest run persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def create_job(
    conn: sqlite3.Connection,
    *,
    display_name: str,
    job_type: str,
    env: str,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    job_id = new_id()
    conn.execute(
        """
        INSERT INTO job(id, display_name, job_type, env, status, params_json, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, datetime('now'))
        """,
        (job_id, display_name, job_type, env, json.dumps(params or {}, ensure_ascii=False)),
    )
    return job_id


def update_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    progress_message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    fields: List[str] = []
    params: List[Any] = []
    if status is not None:
        fields.append("status = ?")
        params.append(status)
        if status == "running":
            fields.append("started_at = datetime('now')")
        if status in ("completed", "failed", "cancelled"):
            fields.append("finished_at = datetime('now')")
    if progress is not None:
        fields.append("progress = ?")
        params.append(progress)
    if progress_message is not None:
        fields.append("progress_message = ?")
        params.append(progress_message)
    if result is not None:
        fields.append("result_json = ?")
        params.append(json.dumps(result, ensure_ascii=False))
    if error is not None:
        fields.append("error_message = ?")
        params.append(error)
    if not fields:
        return
    params.append(job_id)
    conn.execute(f"UPDATE job SET {', '.join(fields)} WHERE id = ?", params)


def get_job(conn: sqlite3.Connection, job_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for key in ("params_json", "result_json"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d


def list_jobs(conn: sqlite3.Connection, limit: int = 20) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM job ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        for key in ("params_json", "result_json"):
            if d.get(key):
                d[key] = json.loads(d[key])
        out.append(d)
    return out


def save_backtest_run(
    conn: sqlite3.Connection,
    *,
    engine: str,
    strategy_id: str,
    title: str,
    params: Dict[str, Any],
    metrics: Dict[str, Any],
    result_path: Optional[str] = None,
) -> str:
    run_id = new_id()
    conn.execute(
        """
        INSERT INTO backtest_run(id, engine, strategy_id, title, params_json, metrics_json, result_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
        """,
        (
            run_id,
            engine,
            strategy_id,
            title,
            json.dumps(params, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False),
            result_path,
        ),
    )
    return run_id


def get_backtest_run(conn: sqlite3.Connection, run_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM backtest_run WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for key in ("params_json", "metrics_json"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d
