"""QMT health check tests."""

from unittest.mock import patch

from qmt_quant.core.qmt_health import check_qmt_connection, ensure_qmt_ready
import pytest


def test_check_qmt_connection_ok():
    with patch(
        "qmt_quant.adapters.qmt.runtime.should_use_x64_bridge",
        return_value=True,
    ), patch(
        "qmt_quant.adapters.qmt.runtime.ping_xtquant",
        return_value={"ok": True, "sector_count": 100, "port": 58610},
    ):
        ok, msg = check_qmt_connection()
    assert ok is True
    assert "58610" in msg


def test_check_qmt_connection_fail():
    with patch(
        "qmt_quant.adapters.qmt.runtime.should_use_x64_bridge",
        return_value=True,
    ), patch(
        "qmt_quant.adapters.qmt.runtime.ping_xtquant",
        return_value={"ok": False},
    ):
        ok, msg = check_qmt_connection()
    assert ok is False
    assert "QMT" in msg


def test_ensure_qmt_ready_raises():
    with patch("qmt_quant.core.qmt_health.check_qmt_connection", return_value=(False, "down")):
        with pytest.raises(RuntimeError, match="down"):
            ensure_qmt_ready()
