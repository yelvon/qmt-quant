"""Exceptions for job execution."""

from __future__ import annotations


class ConcurrentJobError(RuntimeError):
    """Raised when a QMT sync job is already running."""

    def __init__(self, job_id: str, display_name: str) -> None:
        self.job_id = job_id
        self.display_name = display_name
        super().__init__(f"已有同步任务进行中：{display_name}（{job_id[:8]}）")
