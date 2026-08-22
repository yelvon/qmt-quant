"""Pipeline progress tests."""

from types import SimpleNamespace
from unittest.mock import patch

from qmt_quant.core.jobs import runner


def test_pipeline_emits_progress_steps(monkeypatch):
    updates = []

    def fake_report(job_id, progress, message="", **extra):
        updates.append({"progress": progress, "message": message, **extra})

    monkeypatch.setattr(runner, "report_job_progress", fake_report)
    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: SimpleNamespace(
            auto_export_catalog=False,
            sync_incremental_days=5,
            bar_adjust_type="front",
            default_sector="沪深A股",
        ),
    )
    monkeypatch.setattr(runner, "_use_subprocess", lambda env: False)

    with patch("qmt_quant.core.sync.bars.sync_bars", return_value={"ok": True}), patch(
        "qmt_quant.core.sync.index_sync.run_index_sync", return_value={"ok": True}
    ), patch(
        "qmt_quant.core.research.runner.run_research", return_value={"run_id": "r1"}
    ), patch("qmt_quant.core.validation.runner.run_validation", return_value={"run_id": "v1"}):
        out = runner.run_pipeline({}, job_id="job123")

    assert out["validate"]["run_id"] == "v1"
    assert any(u.get("step") == "sync" for u in updates)
    assert any(u.get("step") == "validate" for u in updates)
