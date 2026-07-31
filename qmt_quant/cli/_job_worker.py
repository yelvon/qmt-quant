"""Job worker entry for subprocess dispatch."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict


def main() -> None:
    raw = sys.stdin.read()
    payload = json.loads(raw)
    job_type = payload["job_type"]
    params = payload.get("params") or {}
    result = _dispatch(job_type, params)
    json.dump(result, sys.stdout, ensure_ascii=False)


def _dispatch(job_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if job_type == "sync_bars":
        from qmt_quant.core.sync.bars import sync_bars

        return sync_bars(**params)
    if job_type == "sync_financial":
        from qmt_quant.core.sync.financial import sync_financial

        return sync_financial(**params)
    if job_type == "catalog_export":
        from qmt_quant.core.catalog.export import export_catalog

        return export_catalog(**params)
    if job_type == "research":
        from qmt_quant.core.research.runner import run_research

        return run_research(**params)
    if job_type == "walk_forward":
        from qmt_quant.core.research.walk_forward import run_walk_forward_study

        return run_walk_forward_study(**params)
    if job_type == "validate":
        from qmt_quant.core.validation.runner import run_validation

        return run_validation(**params)
    if job_type == "screen":
        from qmt_quant.core.screener.dsl import load_rule
        from qmt_quant.core.screener.runner import run_screening

        rule_path = params.pop("rule_path", None)
        dsl_rule = load_rule(rule_path) if rule_path else None
        return run_screening(**params, rule=dsl_rule)
    if job_type == "screen_backtest":
        from qmt_quant.core.screener.bridge import run_screen_backtest

        return run_screen_backtest(**params)
    if job_type == "screen_ic":
        from qmt_quant.core.screener.ic import compute_factor_ic

        return compute_factor_ic(**params)
    raise ValueError(f"Unknown job type: {job_type}")


if __name__ == "__main__":
    main()
