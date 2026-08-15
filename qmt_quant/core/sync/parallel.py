"""Parallel batch helpers for QMT sync jobs."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Callable, Generic, List, Optional, Sequence, TypeVar

from qmt_quant.config import get_settings
from qmt_quant.core.jobs.context import is_job_cancelled

T = TypeVar("T")

_qmt_semaphore: Optional[threading.Semaphore] = None
_qmt_semaphore_size = 0


def qmt_semaphore() -> threading.Semaphore:
    """Limit simultaneous QMT bridge/subprocess calls (MiniQMT is usually not thread-safe)."""
    global _qmt_semaphore, _qmt_semaphore_size
    size = max(1, min(int(get_settings().sync_concurrency), 4))
    if _qmt_semaphore is None or _qmt_semaphore_size != size:
        _qmt_semaphore = threading.Semaphore(size)
        _qmt_semaphore_size = size
    return _qmt_semaphore


def reset_qmt_semaphore_for_tests() -> None:
    global _qmt_semaphore, _qmt_semaphore_size
    _qmt_semaphore = None
    _qmt_semaphore_size = 0


def iter_chunks(items: Sequence[str], batch_size: int) -> List[List[str]]:
    size = max(1, batch_size)
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def run_batches_parallel(
    chunks: Sequence[Sequence[str]],
    *,
    concurrency: int,
    job_id: Optional[str],
    cancel_check: Optional[Callable[[], None]] = None,
    worker: Callable[[Sequence[str]], T],
    on_batch_done: Optional[Callable[[int, T], None]] = None,
) -> List[T]:
    """
    Run batch workers with a thread pool.

    Each worker should acquire `qmt_semaphore()` internally if it touches QMT.
    Progress callbacks may arrive out of order when concurrency > 1.
    """
    if not chunks:
        return []
    workers = max(1, min(int(concurrency), len(chunks), 4))
    if workers == 1:
        results: List[T] = []
        for idx, chunk in enumerate(chunks):
            if job_id and is_job_cancelled(job_id):
                if cancel_check:
                    cancel_check()
            result = worker(chunk)
            results.append(result)
            if on_batch_done:
                on_batch_done(idx, result)
        return results

    results: List[Optional[T]] = [None] * len(chunks)
    completed = 0
    lock = threading.Lock()

    def _run(index: int, chunk: Sequence[str]) -> T:
        if job_id and is_job_cancelled(job_id) and cancel_check:
            cancel_check()
        result = worker(chunk)
        nonlocal completed
        with lock:
            results[index] = result
            completed += 1
            if on_batch_done:
                on_batch_done(completed, result)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: dict[Future[T], int] = {
            pool.submit(_run, idx, chunk): idx for idx, chunk in enumerate(chunks)
        }
        pending = set(futures.keys())
        while pending:
            if job_id and is_job_cancelled(job_id) and cancel_check:
                cancel_check()
            done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for future in done:
                futures.pop(future)
                future.result()

    return [r for r in results if r is not None]
