from __future__ import annotations

import json

import pytest

from qmt_quant.core.backtest.experiments import compute_metrics, write_artifacts


def test_metrics_are_complete_and_missing_inputs_are_null():
    metrics = compute_metrics(
        [
            {"date": "2024-01-01", "equity": 100},
            {"date": "2024-01-02", "equity": 110},
            {"date": "2024-01-03", "equity": 99},
        ]
    )
    assert metrics["total_return_pct"] == pytest.approx(-1)
    assert metrics["max_drawdown_pct"] == pytest.approx(-10)
    assert metrics["benchmark_excess_return_pct"] is None
    assert metrics["information_ratio"] is None
    assert metrics["win_rate_pct"] is None
    assert metrics["concentration"] is None


def test_artifacts_use_isolated_run_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("qmt_quant.core.backtest.experiments.ROOT_DIR", tmp_path)
    paths = write_artifacts(
        "run-a",
        manifest={"run_id": "run-a"},
        detail={"metrics": {}},
        equity=[{"date": "2024-01-01", "equity": 100}],
        trades=[],
        positions=[],
    )
    assert json.loads((tmp_path / "reports/run-a/manifest.json").read_text())["run_id"] == "run-a"
    for name in ("detail.json", "equity.json", "trades.json", "positions.json"):
        assert (tmp_path / "reports/run-a" / name).is_file()
    assert paths["artifact_dir"].endswith("run-a")
