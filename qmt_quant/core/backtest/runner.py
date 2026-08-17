"""One-click backtest: research scan then A-share validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.research.runner import run_research
from qmt_quant.core.validation.runner import run_validation


def run_backtest(
    *,
    strategy_id: str = "ma_cross",
    sector: str = "沪深A股",
    range_preset: str = "3y",
    short_preset: str = "preset_std",
    long_preset: str = "preset_std",
    fee_preset: str = "default",
    match_price: str = "next_open",
    benchmark: str = "hs300",
    screen_run_id: Optional[str] = None,
    codes: Optional[list[str]] = None,
    sample: str = "head",
    universe_n: Optional[int] = None,
    signals: Optional[list] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run parameter scan (research) then high-fidelity validation in one job."""
    if strategy_id == "signal_replay":
        if job_id:
            report_job_progress(job_id, 0.2, "按信号表回放…", step="backtest")
        return run_validation(
            strategy_id="signal_replay",
            range_preset=range_preset,
            match_price=match_price,
            benchmark=benchmark,
            codes=codes,
            signals=signals or [],
            job_id=job_id,
        )

    if job_id:
        report_job_progress(
            job_id,
            0.05,
            "快速筛选较优参数…",
            step="scan",
            detail=f"策略 {strategy_id} · 区间 {range_preset}",
        )

    research = run_research(
        strategy_id=strategy_id,
        sector=sector,
        range_preset=range_preset,
        short_preset=short_preset,
        long_preset=long_preset,
        fee_preset=fee_preset,
        screen_run_id=screen_run_id,
        codes=codes,
        sample=sample,
        universe_n=universe_n,
        job_id=None,
    )
    if research.get("error"):
        return research

    research_id = research.get("run_id")
    if not research_id:
        return {"error": "research_save_failed", "message": "参数扫描完成但未保存记录"}
    best = research.get("best") or {}
    if job_id:
        report_job_progress(
            job_id,
            0.55,
            "A 股规则回测…",
            step="backtest",
            detail=str(best.get("label") or "验证中"),
        )

    validate = run_validation(
        from_run_id=research_id,
        match_price=match_price,
        benchmark=benchmark,
        codes=codes,
        job_id=job_id,
    )
    if validate.get("error"):
        return validate

    validate["research_run_id"] = research_id
    validate["research_best"] = best
    result_path = validate.get("result_path")
    if result_path:
        try:
            path = Path(result_path)
            stored = json.loads(path.read_text(encoding="utf-8"))
            stored["research_run_id"] = research_id
            stored["research_best"] = best
            path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    if job_id:
        report_job_progress(job_id, 0.95, "保存回测结果…", step="save")

    return {
        **validate,
        "research_run_id": research_id,
        "research_best": best,
    }
