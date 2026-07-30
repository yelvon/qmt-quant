"""Job runner — dispatches work to qmt-env or quant-env subprocesses."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from qmt_quant.config import get_settings
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import create_job, get_job, update_job

JobHandler = Callable[[Dict[str, Any]], Dict[str, Any]]

_HANDLERS: Dict[str, JobHandler] = {}
_SUBSCRIBERS: List[Callable[[str, Dict[str, Any]], None]] = []


def subscribe(callback: Callable[[str, Dict[str, Any]], None]) -> None:
    _SUBSCRIBERS.append(callback)


def _notify(job_id: str, payload: Dict[str, Any]) -> None:
    for cb in _SUBSCRIBERS:
        try:
            cb(job_id, payload)
        except Exception:
            pass


def register_handler(job_type: str, handler: JobHandler) -> None:
    _HANDLERS[job_type] = handler


def _python_for_env(env: str) -> str:
    settings = get_settings()
    if env == "qmt":
        return settings.qmt_python or sys.executable
    return settings.quant_python or sys.executable


def submit_job(
    *,
    display_name: str,
    job_type: str,
    env: str,
    params: Optional[Dict[str, Any]] = None,
    inline: bool = True,
) -> str:
    run_migrations()
    with db_session() as conn:
        job_id = create_job(
            conn,
            display_name=display_name,
            job_type=job_type,
            env=env,
            params=params,
        )
    if inline:
        thread = threading.Thread(
            target=_execute_job,
            args=(job_id, job_type, env, params or {}),
            daemon=True,
        )
        thread.start()
    return job_id


def _execute_job(job_id: str, job_type: str, env: str, params: Dict[str, Any]) -> None:
    with db_session() as conn:
        update_job(conn, job_id, status="running", progress=0.05)
    _notify(job_id, {"status": "running", "progress": 0.05})
    try:
        handler = _HANDLERS.get(job_type)
        if handler is None:
            result = _dispatch_builtin(job_type, params)
        else:
            result = handler(params)
        with db_session() as conn:
            update_job(conn, job_id, status="completed", progress=1.0, result=result)
        _notify(job_id, {"status": "completed", "progress": 1.0, "result": result})
    except Exception as exc:
        with db_session() as conn:
            update_job(conn, job_id, status="failed", progress=1.0, error=str(exc))
        _notify(job_id, {"status": "failed", "progress": 1.0, "error": str(exc)})


def _dispatch_builtin(job_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if job_type == "sync_bars":
        from qmt_quant.core.sync.bars import sync_bars

        return sync_bars(**params)
    if job_type == "sync_financial":
        from qmt_quant.core.sync.financial import sync_financial

        return sync_financial(**params)
    if job_type == "catalog_export":
        from qmt_quant.core.catalog.export import export_catalog

        return export_catalog(**params)
    if job_type == "research":
        from qmt_quant.core.research.runner import run_research

        return run_research(**params)
    if job_type == "validate":
        from qmt_quant.core.validation.runner import run_validation

        return run_validation(**params)
    if job_type == "screen":
        from qmt_quant.core.screener.runner import run_screening

        return run_screening(**params)
    if job_type == "pipeline":
        return run_pipeline(params)
    raise ValueError(f"Unknown job type: {job_type}")


def run_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    from qmt_quant.core.catalog.export import export_catalog
    from qmt_quant.core.research.runner import run_research
    from qmt_quant.core.sync.bars import sync_bars
    from qmt_quant.core.validation.runner import run_validation

    out: Dict[str, Any] = {}
    out["sync"] = sync_bars(incremental=True, incremental_days=params.get("days", 5))
    if get_settings().auto_export_catalog:
        out["catalog"] = export_catalog()
    out["research"] = run_research(
        strategy_id=params.get("strategy", "ma_cross"),
        range_preset=params.get("range_preset", "3y"),
    )
    research_id = out["research"].get("run_id")
    out["validate"] = run_validation(from_run_id=research_id)
    return out


def fetch_job(job_id: str) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        return get_job(conn, job_id)


def list_recent_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    from qmt_quant.storage.jobs import list_jobs

    with db_session() as conn:
        return list_jobs(conn, limit=limit)
