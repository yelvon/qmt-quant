"""Progress ETA formatting tests."""

from qmt_quant.core.jobs.context import format_eta_seconds, sync_progress_message


def test_format_eta_seconds():
    assert "秒" in format_eta_seconds(30)
    assert "分钟" in format_eta_seconds(120)
    assert "小时" in format_eta_seconds(3700)


def test_sync_progress_message_counts():
    msg = sync_progress_message(10, 100)
    assert "10/100" in msg
