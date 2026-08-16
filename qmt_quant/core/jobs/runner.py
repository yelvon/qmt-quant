"""Job runner — dispatches work to qmt-env or quant-env subprocesses."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from qmt_quant.config import get_settings
from qmt_quant.core.jobs.errors import ConcurrentJobError
from qmt_quant.core.jobs.context import (
    JobCancelled,
    cancel_job,
    is_job_cancelled,
    job_execution,
    report_job_progress,
    request_job_cancel,
    subscribe_progress,
    sync_progress_message,
)
from qmt_quant.core.qmt_health import ensure_qmt_ready
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import create_job, get_job, update_job

JobHandler = Callable[[Dict[str, Any]], Dict[str, Any]]

_HANDLERS: Dict[str, JobHandler] = {}
_SUBSCRIBERS: List[Callable[[str, Dict[str, Any]], None]] = []

QMT_JOB_TYPES = frozenset({"sync_bars", "sync_financial", "sync_repair", "sync_check_repair"})
QMT_SYNC_TYPES = QMT_JOB_TYPES


def _find_running_qmt_job(conn) -> Optional[Dict[str, Any]]:
    placeholders = ",".join(["%s"] * len(QMT_SYNC_TYPES))
    row = conn.execute(
        f"""
        SELECT id, display_name, job_type FROM job
        WHERE status = 'running' AND job_type IN ({placeholders})
        ORDER BY created_at DESC LIMIT 1
        """,
        tuple(QMT_SYNC_TYPES),
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "display_name": row[1], "job_type": row[2]}


def subscribe(callback: Callable[[str, Dict[str, Any]], None]) -> None:
    _SUBSCRIBERS.append(callback)


def _notify(job_id: str, payload: Dict[str, Any]) -> None:
    for cb in _SUBSCRIBERS:
        try:
            cb(job_id, payload)
        except Exception:
            pass


subscribe_progress(_notify)


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


def recover_stale_jobs() -> int:
    """Mark orphaned running jobs as failed after API restart."""
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE job
            SET status = 'failed',
                progress = 1.0,
                error_message = '服务重启导致任务中断，请重新同步',
                finished_at = NOW()
            WHERE status = 'running'
            """
        )
        return cur.rowcount


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
        if job_type in QMT_SYNC_TYPES:
            running = _find_running_qmt_job(conn)
            if running:
                raise ConcurrentJobError(running["id"], running["display_name"])
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


def request_cancel_job(job_id: str) -> bool:
    ok = request_job_cancel(job_id)
    if ok:
        _notify(
            job_id,
            {
                "status": "running",
                "progress": 0.0,
                "message": "正在中断，等待当前批次结束…",
                "cancelling": True,
            },
        )
    return ok


def resume_job(job_id: str) -> str:
    job = fetch_job(job_id)
    if not job:
        raise ValueError("not_found")
    if job.get("status") != "cancelled":
        raise ValueError("job_not_resumable")
    result = job.get("result_json") or {}
    checkpoint = result.get("checkpoint")
    if not checkpoint:
        raise ValueError("no_checkpoint")
    params = dict(job.get("params_json") or {})
    params["resume_checkpoint"] = checkpoint
    sector = str(checkpoint.get("sector") or params.get("sector") or "沪深A股")
    if job.get("job_type") in QMT_JOB_TYPES:
        ensure_qmt_ready(sector)
    display = job.get("display_name", "继续任务")
    if "续传" not in display:
        display = f"{display}（续传）"
    new_id = submit_job(
        display_name=display,
        job_type=str(job.get("job_type", "")),
        env=str(job.get("env", "quant")),
        params=params,
    )
    with db_session() as conn:
        result["checkpoint"] = None
        result["superseded_by"] = new_id
        update_job(conn, job_id, result=result)
    return new_id


def _execute_job(job_id: str, job_type: str, env: str, params: Dict[str, Any]) -> None:
    with job_execution(job_id):
        with db_session() as conn:
            update_job(
                conn,
                job_id,
                status="running",
                progress=0.05,
                progress_message="任务已启动…",
            )
        _notify(
            job_id,
            {"status": "running", "progress": 0.05, "message": "任务已启动…"},
        )
        try:
            work_params = dict(params)
            work_params["job_id"] = job_id
            if _use_subprocess(env):
                result = _run_subprocess(job_type, env, work_params)
            else:
                handler = _HANDLERS.get(job_type)
                if handler is None:
                    if job_type == "pipeline":
                        result = run_pipeline(work_params, job_id=job_id)
                    else:
                        result = _dispatch_builtin(job_type, work_params)
                else:
                    result = handler(work_params)
            with db_session() as conn:
                update_job(
                    conn,
                    job_id,
                    status="completed",
                    progress=1.0,
                    progress_message="已完成",
                    result=result,
                )
            if job_type in QMT_JOB_TYPES or job_type == "data_check":
                from qmt_quant.core.sync.check import clear_data_check_cache

                clear_data_check_cache()
            _notify(
                job_id,
                {
                    "status": "completed",
                    "progress": 1.0,
                    "message": "已完成",
                    "result": result,
                },
            )
        except JobCancelled as exc:
            result = {
                "cancelled": True,
                "checkpoint": exc.checkpoint,
                **exc.partial_result,
            }
            with db_session() as conn:
                update_job(
                    conn,
                    job_id,
                    status="cancelled",
                    progress=exc.progress,
                    progress_message=exc.message,
                    result=result,
                )
            _notify(
                job_id,
                {
                    "status": "cancelled",
                    "progress": exc.progress,
                    "message": exc.message,
                    "result": result,
                },
            )
        except Exception as exc:
            from qmt_quant.storage.db_retry import run_db_retry

            def _mark_failed() -> None:
                with db_session() as conn:
                    update_job(
                        conn,
                        job_id,
                        status="failed",
                        progress=1.0,
                        progress_message="失败",
                        error=str(exc),
                    )

            run_db_retry(_mark_failed)
            _notify(
                job_id,
                {"status": "failed", "progress": 1.0, "error": str(exc), "message": "失败"},
            )


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

        work = dict(params)
        work.pop("days", None)  # legacy alias from older clients
        return sync_bars(**work)
    if job_type == "sync_financial":
        from qmt_quant.core.sync.financial import sync_financial

        return sync_financial(**params)
    if job_type == "sync_repair":
        from qmt_quant.core.sync.gaps import RepairPlan
        from qmt_quant.core.sync.repair import sync_bars_repair

        plan_data = params.pop("repair_plan", None)
        plan = RepairPlan.from_dict(plan_data) if plan_data else None
        if plan is None:
            from qmt_quant.core.sync.gaps import build_repair_plan

            codes = params.pop("codes", None)
            plan = build_repair_plan(
                sector=params.get("sector", "沪深A股"),
                adjust_type=params.get("adjust_type", "front"),
                codes=codes,
            )
        return sync_bars_repair(plan, sector=params.get("sector"), job_id=params.get("job_id"))
    if job_type == "sync_check_repair":
        from qmt_quant.core.sync.repair import run_check_and_repair

        return run_check_and_repair(**params)
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
    if job_type == "backtest":
        from qmt_quant.core.backtest.runner import run_backtest

        return run_backtest(**params)
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
    if job_type == "data_check":
        from qmt_quant.core.sync.check import run_data_check

        return run_data_check(
            sector=params.get("sector", "沪深A股"),
            adjust_type=params.get("adjust_type", "front"),
            detailed=bool(params.get("detailed", True)),
            use_cache=False,
            job_id=params.get("job_id"),
        )
    raise ValueError(f"Unknown job type: {job_type}")


def run_pipeline(params: Dict[str, Any], job_id: Optional[str] = None) -> Dict[str, Any]:
    from qmt_quant.core.catalog.export import export_catalog
    from qmt_quant.core.qmt_health import ensure_qmt_ready
    from qmt_quant.core.research.runner import run_research
    from qmt_quant.core.sync.bars import sync_bars
    from qmt_quant.core.validation.runner import run_validation

    def _step(progress: float, step: str, step_label: str) -> None:
        if not job_id:
            return
        report_job_progress(job_id, progress, step_label, step=step, step_label=step_label)

    out: Dict[str, Any] = {}
    sync_params: Dict[str, Any] = {
        "incremental": True,
        "incremental_days": params.get("days", get_settings().sync_incremental_days),
        "adjust_type": params.get("adjust_type", get_settings().bar_adjust_type),
        "sector": params.get("sector", get_settings().default_sector),
        "job_id": job_id,
    }
    try:
        _step(0.1, "sync", "更新数据")
        if _use_subprocess("qmt"):
            ensure_qmt_ready(sector=str(sync_params["sector"]))
            out["sync"] = _run_subprocess("sync_bars", "qmt", sync_params)
        else:
            out["sync"] = sync_bars(**sync_params)
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
            job_id=job_id,
        )
    except Exception as exc:
        raise RuntimeError(f"[research] {exc}") from exc
    try:
        research_id = out["research"].get("run_id")
        _step(0.8, "validate", "仔细验策略")
        out["validate"] = run_validation(from_run_id=research_id, job_id=job_id)
    except Exception as exc:
        raise RuntimeError(f"[validate] {exc}") from exc
    return out


def fetch_job(job_id: str) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        return get_job(conn, job_id)


def delete_job_by_id(job_id: str) -> Dict[str, Any]:
    from qmt_quant.core.jobs.cleanup import delete_job

    with db_session() as conn:
        return delete_job(conn, job_id)


def cleanup_old_jobs(keep_last: int = 30) -> Dict[str, Any]:
    from qmt_quant.core.jobs.cleanup import cleanup_finished_jobs

    with db_session() as conn:
        return cleanup_finished_jobs(conn, keep_last=keep_last)


def list_recent_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    from qmt_quant.storage.jobs import list_jobs

    with db_session() as conn:
        return list_jobs(conn, limit=limit)


_RESUMABLE_JOB_TYPES = frozenset({"sync_bars", "sync_financial"})


def list_resumable_jobs(limit: int = 5) -> List[Dict[str, Any]]:
    """Return recently cancelled sync jobs that still have a checkpoint."""
    out: List[Dict[str, Any]] = []
    for job in list_recent_jobs(limit=50):
        if job.get("status") != "cancelled":
            continue
        job_type = str(job.get("job_type") or "")
        if job_type not in _RESUMABLE_JOB_TYPES:
            continue
        result = job.get("result_json") or {}
        checkpoint = result.get("checkpoint")
        if not checkpoint:
            continue
        remaining = list(checkpoint.get("remaining_codes") or [])
        if not remaining:
            continue
        processed = int(checkpoint.get("processed") or 0)
        total = int(checkpoint.get("total") or (processed + len(remaining)))
        out.append(
            {
                "job_id": job["id"],
                "job_type": job_type,
                "display_name": job.get("display_name"),
                "progress_message": job.get("progress_message"),
                "progress": float(job.get("progress") or 0),
                "processed": processed,
                "total": total,
                "remaining": len(remaining),
                "sector": checkpoint.get("sector"),
                "start": checkpoint.get("start") or checkpoint.get("start_time"),
                "end": checkpoint.get("end") or checkpoint.get("end_time"),
                "mode": checkpoint.get("mode"),
                "incremental": checkpoint.get("incremental"),
            }
        )
        if len(out) >= limit:
            break
    return out
