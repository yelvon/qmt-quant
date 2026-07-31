"""Job dispatch tests."""

from unittest.mock import patch

from qmt_quant.core.jobs import runner


def test_use_subprocess_when_different_python(monkeypatch):
    monkeypatch.setattr(runner, "get_settings", lambda: type("S", (), {"jobs_inline": False, "qmt_python": "/other/python", "quant_python": ""})())
    monkeypatch.setattr(runner, "sys", __import__("sys"))
    assert runner._use_subprocess("qmt") is True


def test_dispatch_builtin_research():
    with patch("qmt_quant.core.research.runner.run_research", return_value={"ok": True}) as mock:
        out = runner._dispatch_builtin("research", {"strategy_id": "ma_cross"})
    assert out == {"ok": True}
    mock.assert_called_once()
