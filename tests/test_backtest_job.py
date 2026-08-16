"""Backtest job tests."""

from unittest.mock import patch

from qmt_quant.core.backtest.runner import run_backtest
from qmt_quant.core.jobs import runner


def test_run_backtest_passes_codes_to_research_and_validation():
    research_out = {"run_id": "r1", "best": {"label": "10/30", "total_return_pct": 12.5}}
    validate_out = {"run_id": "v1", "total_return_pct": 10.2, "result_path": ""}

    with patch("qmt_quant.core.backtest.runner.run_research", return_value=research_out) as r_mock:
        with patch("qmt_quant.core.backtest.runner.run_validation", return_value=validate_out) as v_mock:
            run_backtest(strategy_id="ma_cross", codes=["600519.SH"], job_id="job-1")

    r_mock.assert_called_once()
    assert r_mock.call_args.kwargs["codes"] == ["600519.SH"]
    v_mock.assert_called_once()
    assert v_mock.call_args.kwargs["codes"] == ["600519.SH"]


def test_dispatch_builtin_backtest():
    with patch("qmt_quant.core.backtest.runner.run_backtest", return_value={"run_id": "v1"}) as mock:
        out = runner._dispatch_builtin("backtest", {"strategy_id": "ma_cross"})
    assert out == {"run_id": "v1"}
    mock.assert_called_once_with(strategy_id="ma_cross")


def test_run_backtest_chains_research_then_validation():
    research_out = {"run_id": "r1", "best": {"label": "10/30", "total_return_pct": 12.5}}
    validate_out = {"run_id": "v1", "total_return_pct": 10.2, "result_path": ""}

    with patch("qmt_quant.core.backtest.runner.run_research", return_value=research_out) as r_mock:
        with patch("qmt_quant.core.backtest.runner.run_validation", return_value=validate_out) as v_mock:
            out = run_backtest(strategy_id="ma_cross", match_price="next_open", job_id="job-1")

    r_mock.assert_called_once()
    assert r_mock.call_args.kwargs["job_id"] is None
    v_mock.assert_called_once_with(
        from_run_id="r1",
        match_price="next_open",
        benchmark="hs300",
        job_id="job-1",
    )
    assert out["run_id"] == "v1"
    assert out["research_run_id"] == "r1"
    assert out["research_best"]["label"] == "10/30"


def test_run_backtest_stops_when_research_has_no_run_id():
    with patch(
        "qmt_quant.core.backtest.runner.run_research",
        return_value={"best": {"label": "10/30"}},
    ):
        with patch("qmt_quant.core.backtest.runner.run_validation") as v_mock:
            out = run_backtest(strategy_id="ma_cross")
    assert out["error"] == "research_save_failed"
    v_mock.assert_not_called()


def test_run_backtest_propagates_research_error():
    with patch(
        "qmt_quant.core.backtest.runner.run_research",
        return_value={"error": "no_price_data"},
    ):
        with patch("qmt_quant.core.backtest.runner.run_validation") as v_mock:
            out = run_backtest(strategy_id="ma_cross")
    assert out["error"] == "no_price_data"
    v_mock.assert_not_called()
