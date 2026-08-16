"""Job dispatch tests."""

from unittest.mock import patch

from qmt_quant.core.jobs import runner


def test_use_subprocess_when_different_python(monkeypatch):
    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: type("S", (), {"jobs_inline": False, "qmt_python": "/other/python", "quant_python": "", "jobs_force_subprocess_for_qmt": True})(),
    )
    monkeypatch.setattr(runner, "sys", __import__("sys"))
    assert runner._use_subprocess("qmt") is True


def test_qmt_force_subprocess_even_when_inline(monkeypatch):
    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: type("S", (), {"jobs_inline": True, "qmt_python": "/qmt/python.exe", "quant_python": "", "jobs_force_subprocess_for_qmt": True})(),
    )
    assert runner._use_subprocess("qmt") is True


def test_quant_inline_when_same_python(monkeypatch):
    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: type("S", (), {"jobs_inline": True, "qmt_python": "", "quant_python": "", "jobs_force_subprocess_for_qmt": True})(),
    )
    assert runner._use_subprocess("quant") is False


def test_dispatch_builtin_research():
    with patch("qmt_quant.core.research.runner.run_research", return_value={"ok": True}) as mock:
        out = runner._dispatch_builtin("research", {"strategy_id": "ma_cross"})
    assert out == {"ok": True}
    mock.assert_called_once()


def test_dispatch_builtin_research_accepts_job_id():
    with patch("qmt_quant.core.research.runner.run_research", return_value={"ok": True}) as mock:
        out = runner._dispatch_builtin(
            "research",
            {"strategy_id": "ma_cross", "job_id": "job-123"},
        )
    assert out == {"ok": True}
    mock.assert_called_once_with(strategy_id="ma_cross", job_id="job-123")


def test_dispatch_builtin_walk_forward():
    with patch("qmt_quant.core.research.walk_forward.run_walk_forward_study", return_value={"segments": []}) as mock:
        out = runner._dispatch_builtin("walk_forward", {"strategy_id": "ma_cross"})
    assert out == {"segments": []}
    mock.assert_called_once()
