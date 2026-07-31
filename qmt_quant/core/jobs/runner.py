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


def _use_subprocess(env: str) -> bool:
    settings = get_settings()
    if env == "qmt" and settings.jobs_force_subprocess_for_qmt and settings.qmt_python:
        return True
    if settings.jobs_inline:
        return False
    py = _python_for_env(env)
    return py != sys.executable and bool(py)


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
        if _use_subprocess(env):
            result = _run_subprocess(job_type, env, params)
        else:
            handler = _HANDLERS.get(job_type)
            if handler is None:
                if job_type == "pipeline":
                    result = run_pipeline(params, job_id=job_id)
                else:
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


def _run_subprocess(job_type: str, env: str, params: Dict[str, Any]) -> Dict[str, Any]:
    py = _python_for_env(env)
    payload = json.dumps({"job_type": job_type, "params": params}, ensure_ascii=False)
    proc = subprocess.run(
        [py, "-m", "qmt_quant.cli._job_worker"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"job failed: {job_type}")
    return json.loads(proc.stdout or "{}")


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
    if job_type == "walk_forward":
        from qmt_quant.core.research.walk_forward import run_walk_forward_study

        return run_walk_forward_study(**params)
    if job_type == "validate":
        from qmt_quant.core.validation.runner import run_validation

        return run_validation(**params)
    if job_type == "screen":
        from qmt_quant.core.screener.dsl import load_rule
        from qmt_quant.core.screener.runner import run_screening

        rule_path = params.pop("rule_path", None)
        dsl_rule = load_rule(rule_path) if rule_path else None
        return run_screening(**params, rule=dsl_rule)
    if job_type == "screen_backtest":
        from qmt_quant.core.screener.bridge import run_screen_backtest

        return run_screen_backtest(**params)
    if job_type == "screen_ic":
        from qmt_quant.core.screener.ic import compute_factor_ic

        return compute_factor_ic(**params)
    raise ValueError(f"Unknown job type: {job_type}")


def run_pipeline(params: Dict[str, Any], job_id: Optional[str] = None) -> Dict[str, Any]:
    from qmt_quant.core.catalog.export import export_catalog
    from qmt_quant.core.research.runner import run_research
    from qmt_quant.core.sync.bars import sync_bars
    from qmt_quant.core.validation.runner import run_validation

    def _step(progress: float, step: str, step_label: str) -> None:
        if not job_id:
            return
        with db_session() as conn:
            update_job(conn, job_id, progress=progress)
        _notify(
            job_id,
            {"status": "running", "progress": progress, "step": step, "step_label": step_label},
        )

    out: Dict[str, Any] = {}
    try:
        _step(0.1, "sync", "更新数据")
        out["sync"] = sync_bars(incremental=True, incremental_days=params.get("days", 5))
    except Exception as exc:
        raise RuntimeError(f"[sync] {exc}") from exc
    try:
        if get_settings().auto_export_catalog:
            _step(0.35, "catalog", "导出验策略文件")
            out["catalog"] = export_catalog()
    except Exception as exc:
        raise RuntimeError(f"[catalog] {exc}") from exc
    try:
        _step(0.55, "research", "快速试策略")
        out["research"] = run_research(
            strategy_id=params.get("strategy", "ma_cross"),
            range_preset=params.get("range_preset", "3y"),
        )
    except Exception as exc:
        raise RuntimeError(f"[research] {exc}") from exc
    try:
        research_id = out["research"].get("run_id")
        _step(0.8, "validate", "仔细验策略")
        out["validate"] = run_validation(from_run_id=research_id)
    except Exception as exc:
        raise RuntimeError(f"[validate] {exc}") from exc
    return out


def fetch_job(job_id: str) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        return get_job(conn, job_id)


def list_recent_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    from qmt_quant.storage.jobs import list_jobs

    with db_session() as conn:
        return list_jobs(conn, limit=limit)
