"""Job and backtest run persistence."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from qmt_quant.storage.database import DbConnection, row_to_dict, rows_to_dicts


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def create_job(
    conn: DbConnection,
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
        VALUES (%s, %s, %s, %s, 'pending', %s, NOW())
        """,
        (job_id, display_name, job_type, env, json.dumps(params or {}, ensure_ascii=False)),
    )
    return job_id


def update_job(
    conn: DbConnection,
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
        fields.append("status = %s")
        params.append(status)
        if status == "running":
            fields.append("started_at = NOW()")
        if status in ("completed", "failed", "cancelled"):
            fields.append("finished_at = NOW()")
    if progress is not None:
        fields.append("progress = %s")
        params.append(progress)
    if progress_message is not None:
        fields.append("progress_message = %s")
        params.append(progress_message)
    if result is not None:
        fields.append("result_json = %s")
        params.append(json.dumps(result, ensure_ascii=False))
    if error is not None:
        fields.append("error_message = %s")
        params.append(error)
    if not fields:
        return
    params.append(job_id)
    conn.execute(f"UPDATE job SET {', '.join(fields)} WHERE id = %s", params)


def get_job(conn: DbConnection, job_id: str) -> Optional[Dict[str, Any]]:
    d = row_to_dict(conn, "SELECT * FROM job WHERE id = %s", (job_id,))
    if not d:
        return None
    for key in ("params_json", "result_json"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d


def list_jobs(conn: DbConnection, limit: int = 20) -> List[Dict[str, Any]]:
    rows = rows_to_dicts(conn, "SELECT * FROM job ORDER BY created_at DESC LIMIT %s", (limit,))
    for d in rows:
        for key in ("params_json", "result_json"):
            if d.get(key):
                d[key] = json.loads(d[key])
    return rows


def save_backtest_run(
    conn: DbConnection,
    *,
    engine: str,
    strategy_id: str,
    title: str,
    params: Dict[str, Any],
    metrics: Dict[str, Any],
    result_path: Optional[str] = None,
    run_id: Optional[str] = None,
    job_id: Optional[str] = None,
    run_kind: str = "validation",
    strategy_version: Optional[str] = None,
    strategy_code_hash: Optional[str] = None,
    settings_snapshot: Optional[Dict[str, Any]] = None,
    data_fingerprint: Optional[Dict[str, Any]] = None,
    universe: Optional[List[str]] = None,
    artifact_dir: Optional[str] = None,
) -> str:
    run_id = run_id or new_id()
    conn.execute(
        """
        INSERT INTO backtest_run(
            id, engine, strategy_id, title, params_json, metrics_json, result_path,
            status, job_id, run_kind, strategy_version, strategy_code_hash,
            settings_json, data_fingerprint_json, universe_json, artifact_dir
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            run_id,
            engine,
            strategy_id,
            title,
            json.dumps(params, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False),
            result_path,
            job_id,
            run_kind,
            strategy_version,
            strategy_code_hash,
            json.dumps(settings_snapshot or {}, ensure_ascii=False),
            json.dumps(data_fingerprint or {}, ensure_ascii=False),
            json.dumps(universe or [], ensure_ascii=False),
            artifact_dir,
        ),
    )
    return run_id


def get_backtest_run(conn: DbConnection, run_id: str) -> Optional[Dict[str, Any]]:
    d = row_to_dict(conn, "SELECT * FROM backtest_run WHERE id = %s", (run_id,))
    if not d:
        return None
    for key in ("params_json", "metrics_json", "settings_json", "data_fingerprint_json", "universe_json"):
        if d.get(key):
            d[key] = json.loads(d[key])
    d["params"] = d.get("params_json") or {}
    d["metrics"] = d.get("metrics_json") or {}
    return d


def list_backtest_runs(
    conn: DbConnection, *, limit: int = 50, run_kind: Optional[str] = None
) -> List[Dict[str, Any]]:
    where, params = "", []
    if run_kind:
        where, params = "WHERE run_kind = %s", [run_kind]
    params.append(max(1, min(int(limit), 500)))
    rows = rows_to_dicts(
        conn, f"SELECT * FROM backtest_run {where} ORDER BY created_at DESC LIMIT %s", params
    )
    for row in rows:
        for key in ("params_json", "metrics_json", "settings_json", "data_fingerprint_json", "universe_json"):
            if row.get(key):
                row[key] = json.loads(row[key])
        row["params"] = row.get("params_json") or {}
        row["metrics"] = row.get("metrics_json") or {}
    return rows
