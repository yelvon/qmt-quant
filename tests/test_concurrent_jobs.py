"""Concurrent QMT job guard tests."""

import pytest

from qmt_quant.core.jobs.errors import ConcurrentJobError
from qmt_quant.core.jobs import runner
from qmt_quant.storage.database import db_session
from qmt_quant.storage.jobs import create_job, update_job


def test_submit_job_rejects_concurrent_sync(db, monkeypatch):
    with db_session(db) as conn:
        job_id = create_job(
            conn,
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params={},
        )
        update_job(conn, job_id, status="running")

    monkeypatch.setattr(runner, "run_migrations", lambda: None)

    with pytest.raises(ConcurrentJobError):
        runner.submit_job(
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params={},
            inline=False,
        )
