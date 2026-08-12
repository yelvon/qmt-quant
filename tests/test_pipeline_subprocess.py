"""Pipeline sync subprocess tests."""

from unittest.mock import patch

from qmt_quant.core.jobs.runner import run_pipeline


def test_pipeline_sync_uses_qmt_subprocess_when_configured():
    with patch("qmt_quant.core.jobs.runner._use_subprocess", return_value=True), patch(
        "qmt_quant.core.qmt_health.ensure_qmt_ready"
    ), patch("qmt_quant.core.jobs.runner._run_subprocess", return_value={"synced": 1}) as mock_sub, patch(
        "qmt_quant.core.catalog.export.export_catalog", return_value={"exported": 0}
    ), patch(
        "qmt_quant.core.research.runner.run_research", return_value={"run_id": "r1"}
    ), patch(
        "qmt_quant.core.validation.runner.run_validation", return_value={"run_id": "v1"}
    ):
        out = run_pipeline({"days": 5, "sector": "沪深A股"})
    assert out["sync"] == {"synced": 1}
    mock_sub.assert_called_once()
    assert mock_sub.call_args[0][0] == "sync_bars"
    assert mock_sub.call_args[0][1] == "qmt"
