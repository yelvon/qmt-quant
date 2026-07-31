"""Data health checks."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from qmt_quant.storage.bars import coverage_stats, quality_stats
from qmt_quant.storage.database import db_session, run_migrations


def run_data_check(
    *,
    as_of_date: Optional[str] = None,
    adjust_type: str = "front",
) -> Dict[str, object]:
    run_migrations()
    as_of = as_of_date or date.today().isoformat()
    with db_session() as conn:
        cov = coverage_stats(conn, adjust_type=adjust_type)
        inst_count = conn.execute("SELECT COUNT(*) FROM instrument").fetchone()[0]
        checks: List[Dict[str, object]] = []

        bar_codes = cov.get("codes", 0) or 0
        coverage_pct = round((bar_codes / inst_count * 100), 1) if inst_count else 0.0
        checks.append(
            {
                "name": "日线是否齐全",
                "ok": coverage_pct >= 90,
                "coverage": f"{coverage_pct}%",
                "detail": f"{bar_codes}/{inst_count} 只股票有日线",
            }
        )
        cal_count = conn.execute("SELECT COUNT(*) FROM trade_calendar").fetchone()[0]
        checks.append(
            {
                "name": "交易日历",
                "ok": cal_count > 0,
                "coverage": "100%" if cal_count else "0%",
                "detail": f"{cal_count} 个交易日记录",
            }
        )
        fin_count = conn.execute(
            "SELECT COUNT(*) FROM financial_pershareindex"
        ).fetchone()[0]
        checks.append(
            {
                "name": "财务披露",
                "ok": fin_count > 0,
                "coverage": "—",
                "detail": f"{fin_count} 条每股指标",
            }
        )
        qstats = quality_stats(conn, adjust_type=adjust_type)
        checks.append(
            {
                "name": "数据质量",
                "ok": qstats["suspicious_pct"] < 5,
                "coverage": f"{100 - qstats['suspicious_pct']}%",
                "detail": f"bad={qstats['bad_bars_count']}, suspicious={qstats['suspicious_bars_count']}",
            }
        )
        return {
            "as_of": as_of,
            "adjust_type": adjust_type,
            "checks": checks,
            "bar_coverage_pct": coverage_pct,
            "quality": qstats,
            "summary_ok": all(c["ok"] for c in checks[:2]),
        }
