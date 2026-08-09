"""Job cancel / resume tests."""

from unittest.mock import MagicMock, patch

import pytest

from qmt_quant.core.jobs.context import JobCancelled
from qmt_quant.core.jobs import runner
from qmt_quant.storage.database import db_session, run_migrations


def test_cancel_job_sets_flag(tmp_path, monkeypatch):
    db_file = tmp_path / "cancel.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    from qmt_quant.storage.jobs import create_job, update_job

    with db_session(db_file) as conn:
        job_id = create_job(
            conn,
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params={},
        )
        update_job(conn, job_id, status="running")
    from qmt_quant.core.jobs.context import is_job_cancelled, request_job_cancel

    assert request_job_cancel(job_id)
    assert is_job_cancelled(job_id)
    config._settings = None


def test_resume_job_requires_checkpoint(monkeypatch):
    monkeypatch.setattr(
        runner,
        "fetch_job",
        lambda job_id: {
            "id": job_id,
            "status": "cancelled",
            "display_name": "更新行情",
            "job_type": "sync_bars",
            "env": "qmt",
            "params_json": {"sector": "沪深A股"},
            "result_json": {},
        },
    )
    with pytest.raises(ValueError, match="no_checkpoint"):
        runner.resume_job("abc")


def test_resume_job_submits_with_checkpoint(monkeypatch):
    checkpoint = {
        "remaining_codes": ["600519.SH"],
        "processed": 1,
        "total": 2,
        "start": "2026-08-01",
        "end": "2026-08-09",
        "sector": "沪深A股",
        "adjust_type": "front",
        "mode": "incremental",
    }
    monkeypatch.setattr(
        runner,
        "fetch_job",
        lambda job_id: {
            "id": job_id,
            "status": "cancelled",
            "display_name": "更新行情",
            "job_type": "sync_bars",
            "env": "qmt",
            "params_json": {"sector": "沪深A股", "incremental": True},
            "result_json": {"checkpoint": checkpoint},
        },
    )
    monkeypatch.setattr(runner, "ensure_qmt_ready", lambda sector="沪深A股": None)
    submitted = {}

    def fake_submit(**kwargs):
        submitted.update(kwargs)
        return "new-job-id"

    monkeypatch.setattr(runner, "submit_job", fake_submit)
    new_id = runner.resume_job("old-job")
    assert new_id == "new-job-id"
    assert submitted["params"]["resume_checkpoint"] == checkpoint


def test_fetch_and_upsert_raises_on_cancel(tmp_path, monkeypatch):
    db_file = tmp_path / "fetch.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    from qmt_quant.core.sync.repair import _fetch_and_upsert
    from qmt_quant.core.jobs.context import request_job_cancel
    from qmt_quant.storage.jobs import create_job, update_job

    with db_session(db_file) as conn:
        job_id = create_job(
            conn,
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params={},
        )
        update_job(conn, job_id, status="running")
    request_job_cancel(job_id)
    client = MagicMock()
    conn = MagicMock()
    with pytest.raises(JobCancelled) as exc:
        _fetch_and_upsert(
            client,
            conn,
            ["600519.SH", "000001.SZ"],
            "2026-08-01",
            "2026-08-09",
            "front",
            "front",
            50,
            job_id=job_id,
            sector="沪深A股",
            mode="incremental",
        )
    assert exc.value.checkpoint["total"] == 2
    config._settings = None
