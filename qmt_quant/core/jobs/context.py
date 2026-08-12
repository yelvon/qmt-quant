"""Job execution context: progress reporting and cooperative cancellation."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

import psycopg

from qmt_quant.storage.database import db_session
from qmt_quant.storage.db_retry import is_transient_db_error
from qmt_quant.storage.jobs import update_job

_CANCEL_FLAGS: Dict[str, threading.Event] = {}
_PROGRESS_HOOKS: list = []
_JOB_STARTED: Dict[str, float] = {}
_tls = threading.local()


class JobCancelled(Exception):
    """Raised when a job is cancelled; carries checkpoint for resume."""

    def __init__(
        self,
        checkpoint: Dict[str, Any],
        *,
        progress: float = 0.0,
        partial_result: Optional[Dict[str, Any]] = None,
        message: str = "用户已中断同步",
    ) -> None:
        super().__init__(message)
        self.checkpoint = checkpoint
        self.progress = progress
        self.partial_result = partial_result or {}
        self.message = message


def format_eta_seconds(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return ""
    if seconds < 60:
        return f"约 {max(1, seconds)} 秒"
    if seconds < 3600:
        mins = max(1, seconds // 60)
        return f"约 {mins} 分钟"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    if mins:
        return f"约 {hours} 小时 {mins} 分钟"
    return f"约 {hours} 小时"


def estimate_eta_seconds(job_id: str, progress: float) -> Optional[int]:
    if progress < 0.08:
        return None
    started = _JOB_STARTED.get(job_id)
    if not started:
        return None
    elapsed = time.monotonic() - started
    if progress <= 0:
        return None
    return max(0, int(elapsed / progress * (1 - progress)))


def sync_progress_message(
    processed: int,
    total: int,
    *,
    job_id: Optional[str] = None,
    prefix: str = "已同步",
    progress: Optional[float] = None,
) -> str:
    msg = f"{prefix} {processed}/{total} 只股票"
    if job_id and total > 0:
        pct = progress if progress is not None else (0.05 + 0.90 * (processed / total))
        eta = estimate_eta_seconds(job_id, pct)
        if eta is not None:
            msg += f" · 预计剩余 {format_eta_seconds(eta)}"
    return msg


def register_cancel_flag(job_id: str) -> threading.Event:
    flag = threading.Event()
    _CANCEL_FLAGS[job_id] = flag
    return flag


def clear_cancel_flag(job_id: str) -> None:
    _CANCEL_FLAGS.pop(job_id, None)
    _JOB_STARTED.pop(job_id, None)


def _persist_cancel_request(job_id: str) -> None:
    with db_session() as conn:
        try:
            conn.execute(
                "UPDATE job SET cancel_requested = TRUE WHERE id = %s AND status = 'running'",
                (job_id,),
            )
        except psycopg.Error:
            pass


def _db_cancel_requested(job_id: str) -> bool:
    with db_session() as conn:
        try:
            row = conn.execute(
                "SELECT cancel_requested FROM job WHERE id = %s AND status = 'running'",
                (job_id,),
            ).fetchone()
        except psycopg.Error:
            return False
        return bool(row and row[0])


def request_job_cancel(job_id: str) -> bool:
    with db_session() as conn:
        row = conn.execute(
            "SELECT status FROM job WHERE id = %s",
            (job_id,),
        ).fetchone()
        if not row or row[0] != "running":
            return False
    _persist_cancel_request(job_id)
    if job_id not in _CANCEL_FLAGS:
        register_cancel_flag(job_id)
    _CANCEL_FLAGS[job_id].set()
    return True


def cancel_job(job_id: str) -> bool:
    return request_job_cancel(job_id)


def is_job_cancelled(job_id: Optional[str]) -> bool:
    if not job_id:
        return False
    flag = _CANCEL_FLAGS.get(job_id)
    if flag is not None and flag.is_set():
        return True
    if _db_cancel_requested(job_id):
        if job_id not in _CANCEL_FLAGS:
            register_cancel_flag(job_id)
        _CANCEL_FLAGS[job_id].set()
        return True
    return False


def subscribe_progress(callback) -> None:
    _PROGRESS_HOOKS.append(callback)


def _emit_progress(job_id: str, payload: Dict[str, Any]) -> None:
    for hook in _PROGRESS_HOOKS:
        try:
            hook(job_id, payload)
        except Exception:
            pass


def report_job_progress(
    job_id: Optional[str],
    progress: float,
    message: str = "",
    **extra: Any,
) -> None:
    if not job_id:
        return
    if job_id not in _JOB_STARTED:
        _JOB_STARTED[job_id] = time.monotonic()
    eta_seconds = estimate_eta_seconds(job_id, progress)
    for attempt in range(5):
        try:
            with db_session() as conn:
                update_job(conn, job_id, progress=progress, progress_message=message)
            break
        except psycopg.Error as exc:
            if not is_transient_db_error(exc) or attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))
    payload: Dict[str, Any] = {
        "status": "running",
        "progress": progress,
        "message": message,
        **extra,
    }
    if eta_seconds is not None:
        payload["eta_seconds"] = eta_seconds
    _emit_progress(job_id, payload)


@contextmanager
def job_execution(job_id: str) -> Iterator[str]:
    register_cancel_flag(job_id)
    _tls.job_id = job_id
    try:
        yield job_id
    finally:
        _tls.job_id = None
        clear_cancel_flag(job_id)


def current_job_id() -> Optional[str]:
    return getattr(_tls, "job_id", None)
