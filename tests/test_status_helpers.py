"""Status action builder tests."""

from qmt_quant.web.status_helpers import build_status_actions


def test_actions_fix_env_when_doctor_fails():
    actions = build_status_actions(
        doctor_ok=False,
        checks=[{"name": "qmt_python_for_jobs", "ok": False, "message": "WARN: not configured"}],
        bar_coverage_pct=0,
    )
    assert actions[0]["id"] == "fix_env"
    assert actions[0]["route"] == "/settings"


def test_actions_sync_when_low_coverage():
    actions = build_status_actions(
        doctor_ok=True,
        checks=[],
        bar_coverage_pct=30,
    )
    assert any(a["id"] == "sync_data" for a in actions)


def test_actions_repair_when_needs_repair():
    actions = build_status_actions(
        doctor_ok=True,
        checks=[],
        bar_coverage_pct=90,
        needs_repair=True,
    )
    assert any(a["id"] == "repair_data" for a in actions)


def test_actions_try_strategy_when_ready():
    actions = build_status_actions(
        doctor_ok=True,
        checks=[],
        bar_coverage_pct=90,
    )
    ids = [a["id"] for a in actions]
    assert "try_strategy" in ids


def test_has_strategy_run_false_on_empty(db):
    from qmt_quant.web.status_helpers import has_strategy_run

    assert has_strategy_run() is False
