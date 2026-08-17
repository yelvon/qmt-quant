"""Build dashboard action cards from doctor/data status."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from qmt_quant.storage.database import db_session


def build_status_actions(
    *,
    doctor_ok: bool,
    checks: List[Dict[str, Any]],
    bar_coverage_pct: float,
    needs_repair: bool = False,
) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []

    qmt_py_fail = any(c.get("name") == "qmt_python_for_jobs" and not c.get("ok") for c in checks)
    if not doctor_ok or qmt_py_fail:
        reason = "QMT 环境或路径未就绪"
        for c in checks:
            if not c.get("ok") and c.get("name") in ("xtquant", "qmt_install_dir", "qmt_python_for_jobs"):
                reason = str(c.get("message", reason))[:80]
                break
        actions.append(
            {
                "id": "fix_env",
                "label": "配置 QMT 环境",
                "route": "/settings",
                "reason": reason,
            }
        )

    if needs_repair:
        actions.append(
            {
                "id": "repair_data",
                "label": "修复数据缺口",
                "route": "/data",
                "reason": "检测到行情滞后或缺日，建议一键修复",
            }
        )
    elif bar_coverage_pct < 80:
        actions.append(
            {
                "id": "sync_data",
                "label": "更新今日数据",
                "route": "/data",
                "reason": f"行情覆盖 {bar_coverage_pct}%，建议先同步",
            }
        )
    elif doctor_ok:
        actions.append(
            {
                "id": "try_strategy",
                "label": "快速试策略",
                "route": "/research",
                "reason": "数据已就绪，可以开始参数扫描",
            }
        )
        actions.append(
            {
                "id": "validate",
                "label": "仔细验策略",
                "route": "/validation",
                "reason": "已有研究记录时，用真实规则复核",
            }
        )

    return actions[:3]


def has_strategy_run() -> bool:
    """True when the user has completed a research/backtest/validate run."""
    with db_session() as conn:
        row = conn.execute("SELECT 1 FROM backtest_run LIMIT 1").fetchone()
        if row:
            return True
        row = conn.execute(
            """
            SELECT 1 FROM job
            WHERE status = 'completed'
              AND job_type IN ('research', 'backtest', 'validate', 'walk_forward')
            LIMIT 1
            """
        ).fetchone()
        return row is not None
