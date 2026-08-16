"""Tests for job deletion and artifact cleanup."""

from __future__ import annotations

from qmt_quant.config import ROOT_DIR
from qmt_quant.storage.database import db_session
from qmt_quant.storage.jobs import create_job, get_job, update_job


def _create_finished_job(conn, *, job_type: str, result: dict) -> str:
    job_id = create_job(
        conn,
        display_name="test job",
        job_type=job_type,
        env="quant",
        params={},
    )
    update_job(conn, job_id, status="completed", progress=1.0, result=result)
    return job_id


def test_delete_job_removes_record_and_report_file(db):
    report = ROOT_DIR / "reports" / "test_delete_job.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('{"ok": true}', encoding="utf-8")

    with db_session(db) as conn:
        job_id = _create_finished_job(
            conn,
            job_type="screen_ic",
            result={"result_path": str(report)},
        )

    from fastapi.testclient import TestClient
    from qmt_quant.web.app import create_app

    res = TestClient(create_app()).delete(f"/api/jobs/{job_id}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True
    assert not report.exists()

    with db_session(db) as conn:
        assert get_job(conn, job_id) is None


def test_delete_job_removes_backtest_run(db):
    run_id = "bt_test_run_1"
    report = ROOT_DIR / "reports" / "research_test.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{}", encoding="utf-8")

    with db_session(db) as conn:
        conn.execute(
            """
            INSERT INTO backtest_run(id, strategy_id, params_json, metrics_json, result_path)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (run_id, "ma_cross", "{}", "{}", str(report)),
        )
        job_id = _create_finished_job(
            conn,
            job_type="research",
            result={"run_id": run_id, "result_path": str(report)},
        )

    from fastapi.testclient import TestClient
    from qmt_quant.web.app import create_app

    res = TestClient(create_app()).delete(f"/api/jobs/{job_id}")
    assert res.status_code == 200
    assert res.json()["backtest_runs_deleted"] == 1
    assert not report.exists()

    with db_session(db) as conn:
        assert get_job(conn, job_id) is None
        assert conn.execute("SELECT 1 FROM backtest_run WHERE id=%s", (run_id,)).fetchone() is None


def test_delete_job_removes_screening_rows(db):
    run_id = "scr_test_run_1"
    with db_session(db) as conn:
        conn.execute(
            """
            INSERT INTO screening_result(run_id, as_of_date, code, score, reason, rank_no)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (run_id, "2024-01-02", "600519.SH", 1.0, "test", 1),
        )
        job_id = _create_finished_job(
            conn,
            job_type="screen",
            result={"run_id": run_id, "count": 1},
        )

    from fastapi.testclient import TestClient
    from qmt_quant.web.app import create_app

    res = TestClient(create_app()).delete(f"/api/jobs/{job_id}")
    assert res.status_code == 200
    assert res.json()["screening_rows_deleted"] == 1

    with db_session(db) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM screening_result WHERE run_id=%s",
            (run_id,),
        ).fetchone()[0]
        assert rows == 0


def test_cannot_delete_running_job(db):
    with db_session(db) as conn:
        job_id = create_job(
            conn,
            display_name="running",
            job_type="research",
            env="quant",
            params={},
        )
        update_job(conn, job_id, status="running", progress=0.5)

    from fastapi.testclient import TestClient
    from qmt_quant.web.app import create_app

    res = TestClient(create_app()).delete(f"/api/jobs/{job_id}")
    assert res.status_code == 400
    assert res.json()["detail"] == "job_still_active"


def test_cleanup_old_jobs(db):
    with db_session(db) as conn:
        ids = []
        for i in range(5):
            jid = _create_finished_job(conn, job_type="research", result={"n": i})
            ids.append(jid)

    from fastapi.testclient import TestClient
    from qmt_quant.web.app import create_app

    res = TestClient(create_app()).post("/api/jobs/cleanup", json={"keep_last": 2})
    assert res.status_code == 200
    assert res.json()["jobs_deleted"] == 3

    with db_session(db) as conn:
        remaining = conn.execute("SELECT COUNT(*) FROM job").fetchone()[0]
        assert remaining == 2
