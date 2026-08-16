"""Data check job dispatch."""

from __future__ import annotations

from unittest.mock import patch

from qmt_quant.core.jobs.runner import _dispatch_builtin


def test_dispatch_data_check_passes_job_id():
    seen = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"summary_ok": True, "checks": []}

    with patch("qmt_quant.core.sync.check.run_data_check", side_effect=fake_run):
        out = _dispatch_builtin(
            "data_check",
            {
                "sector": "沪深A股",
                "adjust_type": "front",
                "detailed": True,
                "job_id": "job123",
            },
        )

    assert out["summary_ok"] is True
    assert seen["job_id"] == "job123"
    assert seen["use_cache"] is False
    assert seen["detailed"] is True
