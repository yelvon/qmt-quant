"""Stock screening runner."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from qmt_quant.core.catalog.export import load_price_matrix
from qmt_quant.core.jobs.context import report_job_progress
from qmt_quant.core.screener.dsl import ScreeningRule, rule_from_template
from qmt_quant.core.screener.rules import apply_rules
from qmt_quant.core.screener.templates import TEMPLATES
from qmt_quant.core.sync.universe import list_days_since, resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import load_financial_asof


def run_screening(
    *,
    template_id: str = "low_pe",
    top_n: int = 30,
    sector: str = "沪深A股",
    exclude_st: bool = True,
    pe_max: Optional[float] = None,
    roe_min: Optional[float] = None,
    ma_window: Optional[int] = None,
    list_days_lt: Optional[int] = 120,
    rule: Optional[ScreeningRule] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_migrations()
    if rule is None:
        rule = rule_from_template(template_id)
    template = TEMPLATES.get(template_id, TEMPLATES["low_pe"])
    pe_limit = pe_max if pe_max is not None else rule.pe_max or template.pe_max
    roe_limit = roe_min if roe_min is not None else rule.roe_min or template.roe_min
    ma_w = ma_window if ma_window is not None else rule.ma_window or template.ma_window
    list_min_days = list_days_lt if list_days_lt is not None else rule.list_days_lt
    exclude_st = rule.exclude_st if rule.exclude_st is not None else exclude_st
    top_n = rule.top_n or top_n
    as_of = rule.as_of or date.today().isoformat()

    if job_id:
        report_job_progress(
            job_id,
            0.1,
            "加载股票池与行情…",
            step="load",
            detail=f"模板 {template_id} · {sector}",
        )
    codes = resolve_universe(sector)
    prices = load_price_matrix(codes=codes[:800] if codes else None)
    if prices.empty:
        return {"error": "no_price_data", "results": []}

    rows: List[Dict[str, Any]] = []
    skipped_no_financial = 0
    skipped_list_days = 0
    columns = list(prices.columns)
    total = len(columns)
    with db_session() as conn:
        for i, code in enumerate(columns):
            if job_id and (i == 0 or i % 50 == 0 or i == total - 1):
                report_job_progress(
                    job_id,
                    0.15 + 0.55 * (i / max(total, 1)),
                    f"扫描股票 {i + 1}/{total}",
                    step="scan",
                    detail=f"PE≤{pe_limit} · ROE≥{roe_limit}",
                )
            name_row = conn.execute(
                "SELECT name, is_st, list_date FROM instrument WHERE code=%s", (code,)
            ).fetchone()
            name = name_row[0] if name_row else code.split(".")[0]
            is_st = bool(name_row[1]) if name_row else ("ST" in name.upper())
            list_date = name_row[2] if name_row else None
            if exclude_st and is_st:
                continue
            if list_min_days is not None:
                days = list_days_since(list_date, as_of)
                if days is not None and days < list_min_days:
                    skipped_list_days += 1
                    continue
            fin = load_financial_asof(conn, "Pershareindex", code, as_of) or {}
            pe = _num(fin.get("pe") or fin.get("s_fa_pe") or fin.get("pe_ttm"))
            roe = _num(fin.get("roe") or fin.get("s_fa_roe"))
            if pe is None or roe is None:
                skipped_no_financial += 1
                continue
            mom = float(prices[code].pct_change(ma_w).iloc[-1] or 0)
            ma5 = float(prices[code].rolling(5).mean().iloc[-1] or 0)
            ma20 = float(prices[code].rolling(20).mean().iloc[-1] or 0)
            above_ma = prices[code].iloc[-1] > prices[code].rolling(ma_w).mean().iloc[-1]
            if rule.ma_bullish and not above_ma:
                continue
            if template_id in ("ma_bull", "ma_bullish") and not above_ma:
                continue
            if pe > pe_limit or roe < roe_limit:
                continue
            score = round(0.4 * (1 - min(pe, 100) / 100) + 0.3 * max(mom, 0) + 0.3 * roe, 4)
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "pe": pe,
                    "roe": roe,
                    "momentum_20d": round(mom * 100, 2),
                    "ma5": ma5,
                    "ma20": ma20,
                    "score": score,
                }
            )

    try:
        import polars as pl

        if job_id:
            report_job_progress(job_id, 0.78, f"排序并选取 Top {top_n}…", step="rank")
        df = pl.DataFrame(rows)
        selected_df = apply_rules(
            df,
            {
                "exclude_st": exclude_st,
                "max_pe": pe_limit,
                "min_roe": roe_limit,
                "ma_bullish": rule.ma_bullish or template_id in ("ma_bull", "ma_bullish"),
                "sort_by": rule.rank_by or "score",
            },
            top_n=top_n,
        )
        selected = selected_df.to_dicts()
    except ImportError:
        rows.sort(key=lambda r: r["score"], reverse=True)
        selected = rows[:top_n]

    run_id = uuid.uuid4().hex[:12]
    reason = rule.name or template.name
    if job_id:
        report_job_progress(job_id, 0.92, "写入选股结果…", step="rank", detail=f"入选 {len(selected)} 只")
    with db_session() as conn:
        for i, row in enumerate(selected, start=1):
            conn.execute(
                """
                INSERT INTO screening_result(run_id, as_of_date, code, score, reason, rank_no)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, as_of, row["code"], row["score"], reason, i),
            )

    return {
        "run_id": run_id,
        "template": template_id,
        "top_n": top_n,
        "count": len(selected),
        "skipped_no_financial": skipped_no_financial,
        "skipped_list_days": skipped_list_days,
        "results": selected,
    }


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None
