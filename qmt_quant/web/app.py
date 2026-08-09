"""FastAPI application for qmt-quant web UI."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from qmt_quant.config import get_settings
from qmt_quant.core.data.kline import build_kline_payload
from qmt_quant.core.data.query import get_date_range, list_available_adjust_types, query_table
from qmt_quant.core.data.table_meta import get_table_meta, list_tables
from qmt_quant.core.doctor import run_doctor
from qmt_quant.core.jobs.runner import fetch_job, list_recent_jobs, submit_job, subscribe
from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.research.presets import (
    FEE_PRESETS,
    LONG_MA_PRESETS,
    RANGE_PRESETS,
    SHORT_MA_PRESETS,
)
from qmt_quant.core.screener.templates import TEMPLATES
from qmt_quant.core.sync.check import run_data_check
from qmt_quant.core.trade.service import get_trade_status, preview_signal_orders, submit_orders
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.jobs import get_backtest_run, list_jobs
from qmt_quant.web.status_helpers import build_status_actions


class SyncBarsBody(BaseModel):
    sector: str = "沪深A股"
    incremental: bool = True
    days: int = 5
    adjust: str = "front"
    range_preset: Optional[str] = None


class WalkForwardBody(BaseModel):
    strategy: str = "ma_cross"
    sector: str = "沪深A股"
    range_preset: str = "3y"
    short_preset: str = "preset_std"
    long_preset: str = "preset_std"
    train_months: int = 12
    test_months: int = 3


class ScreenIcBody(BaseModel):
    template: str = "low_pe"
    sector: str = "沪深A股"


class SyncFinancialBody(BaseModel):
    sector: str = "沪深A股"
    tables: List[str] = Field(default_factory=lambda: ["Balance", "Income", "CashFlow", "Pershareindex"])
    incremental: bool = True


class SyncRepairBody(BaseModel):
    sector: str = "沪深A股"
    adjust: str = "front"
    codes: Optional[List[str]] = None


class SyncCheckRepairBody(BaseModel):
    sector: str = "沪深A股"
    adjust: str = "front"
    detailed: bool = True


class ResearchBody(BaseModel):
    strategy: str = "ma_cross"
    sector: str = "沪深A股"
    range_preset: str = "3y"
    short_preset: str = "preset_std"
    long_preset: str = "preset_std"
    fee_preset: str = "default"
    screen_run_id: Optional[str] = None


class ValidateBody(BaseModel):
    from_run: Optional[str] = None
    strategy: str = "ma_cross"
    short: int = 20
    long: int = 120
    match: str = "next_open"
    benchmark: str = "hs300"
    screen_run_id: Optional[str] = None


class ScreenBody(BaseModel):
    template: str = "low_pe"
    top: int = 30
    sector: str = "沪深A股"
    exclude_st: bool = True
    pe_max: Optional[float] = None
    roe_min: Optional[float] = None
    rule_path: Optional[str] = None


class ScreenBacktestBody(BaseModel):
    run_id: str
    engine: str = "vectorbt"
    range_preset: str = "3y"


class SettingsBody(BaseModel):
    qmt_install_dir: Optional[str] = None
    qmt_python: Optional[str] = None
    quant_python: Optional[str] = None
    userdata_path: Optional[str] = None
    account_id: Optional[str] = None
    dry_run: Optional[bool] = None
    commission_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    sync_auto_repair: Optional[bool] = None


class TradeBody(BaseModel):
    codes: List[str]
    side: str = "buy"
    quantity: int = 100
    live: bool = False
    confirm: Optional[str] = None


class JobManager:
    def __init__(self) -> None:
        self.connections: Set[WebSocket] = set()

    async def broadcast(self, job_id: str, payload: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        message = json.dumps({"job_id": job_id, **payload}, ensure_ascii=False)
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.discard(ws)


job_manager = JobManager()


def _on_job_update(job_id: str, payload: Dict[str, Any]) -> None:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(job_manager.broadcast(job_id, payload))
    except RuntimeError:
        pass


subscribe(_on_job_update)


def create_app() -> FastAPI:
    run_migrations()
    app = FastAPI(title="qmt-quant", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/status")
    def api_status() -> Dict[str, Any]:
        doctor = run_doctor()
        check = run_data_check()
        jobs = list_recent_jobs(5)
        coverage = float(check.get("bar_coverage_pct", 0) or 0)
        suggestion = "更新今日数据"
        if coverage > 80:
            suggestion = "快速试策略"
        checks = [c.__dict__ for c in doctor.checks]
        actions = build_status_actions(
            doctor_ok=doctor.ok,
            checks=checks,
            bar_coverage_pct=coverage,
            needs_repair=bool(check.get("needs_repair")),
        )
        return {
            "doctor_ok": doctor.ok,
            "checks": checks,
            "data_check": check,
            "recent_jobs": jobs,
            "suggestion": suggestion,
            "actions": actions,
            "onboarding_complete": doctor.ok and coverage > 80,
        }

    @app.get("/api/doctor")
    def api_doctor() -> Dict[str, Any]:
        doctor = run_doctor()
        return {
            "ok": doctor.ok,
            "checks": [c.__dict__ for c in doctor.checks],
        }

    @app.get("/api/data/check")
    def api_data_check(
        detailed: bool = False,
        sector: str = "沪深A股",
        adjust: str = "front",
    ) -> Dict[str, Any]:
        return run_data_check(sector=sector, adjust_type=adjust, detailed=detailed)

    @app.get("/api/data/meta")
    def api_data_meta(table: str) -> Dict[str, Any]:
        try:
            meta = get_table_meta(table)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with db_session() as conn:
            meta["available_adjust_types"] = list_available_adjust_types(conn)
        return {"ok": True, **meta}

    @app.get("/api/data/tables")
    def api_data_tables() -> Dict[str, Any]:
        return {"tables": list_tables()}

    @app.get("/api/data/query")
    def api_data_query(
        table: str,
        view_mode: str,
        date: Optional[str] = None,
        code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        adjust: str = "front",
        q: Optional[str] = None,
        exclude_st: bool = False,
        page: int = 1,
        page_size: int = 100,
        sort_col: Optional[str] = None,
        sort_dir: str = "asc",
    ) -> Dict[str, Any]:
        try:
            with db_session() as conn:
                result = query_table(
                    conn,
                    table,
                    view_mode,
                    date=date,
                    code=code,
                    date_from=date_from,
                    date_to=date_to,
                    adjust_type=adjust,
                    q=q,
                    exclude_st=exclude_st,
                    page=page,
                    page_size=page_size,
                    sort_col=sort_col,
                    sort_dir=sort_dir,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **result}

    @app.get("/api/data/kline")
    def api_data_kline(
        code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        adjust: str = "front",
    ) -> Dict[str, Any]:
        try:
            with db_session() as conn:
                return build_kline_payload(conn, code, date_from, date_to, adjust)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/data/dates")
    def api_data_dates(adjust: str = "front") -> Dict[str, Any]:
        try:
            with db_session() as conn:
                return {"ok": True, **get_date_range(conn, adjust)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/jobs/sync/bars")
    def job_sync_bars(body: SyncBarsBody) -> Dict[str, str]:
        params: Dict[str, Any] = {
            "sector": body.sector,
            "incremental": body.incremental,
            "incremental_days": body.days,
            "adjust_type": body.adjust,
        }
        if body.range_preset and not body.incremental:
            start, _ = resolve_range_preset(body.range_preset)
            params["start_date"] = start
            params["incremental"] = False
        job_id = submit_job(
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params=params,
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/sync/financial")
    def job_sync_financial(body: SyncFinancialBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="同步财报",
            job_type="sync_financial",
            env="qmt",
            params={
                "sector": body.sector,
                "tables": body.tables,
                "incremental": body.incremental,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/sync/repair")
    def job_sync_repair(body: SyncRepairBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="修复数据缺口",
            job_type="sync_repair",
            env="qmt",
            params={
                "sector": body.sector,
                "adjust_type": body.adjust,
                "codes": body.codes,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/sync/check-repair")
    def job_sync_check_repair(body: SyncCheckRepairBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="检查并修复数据",
            job_type="sync_check_repair",
            env="qmt",
            params={
                "sector": body.sector,
                "adjust_type": body.adjust,
                "detailed": body.detailed,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/catalog/export")
    def job_catalog_export() -> Dict[str, str]:
        job_id = submit_job(
            display_name="导出验策略文件",
            job_type="catalog_export",
            env="quant",
            params={"adjust_type": get_settings().bar_adjust_type},
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/research")
    def job_research(body: ResearchBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="快速试策略",
            job_type="research",
            env="quant",
            params={
                "strategy_id": body.strategy,
                "sector": body.sector,
                "range_preset": body.range_preset,
                "short_preset": body.short_preset,
                "long_preset": body.long_preset,
                "fee_preset": body.fee_preset,
                "screen_run_id": body.screen_run_id,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/research/walk-forward")
    def job_walk_forward(body: WalkForwardBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="Walk-Forward 稳健性",
            job_type="walk_forward",
            env="quant",
            params={
                "strategy_id": body.strategy,
                "sector": body.sector,
                "range_preset": body.range_preset,
                "short_preset": body.short_preset,
                "long_preset": body.long_preset,
                "train_bars": body.train_months * 21,
                "test_bars": body.test_months * 21,
            },
        )
        return {"job_id": job_id}

    @app.get("/api/research/{run_id}")
    def api_research(run_id: str) -> Dict[str, Any]:
        with db_session() as conn:
            run = get_backtest_run(conn, run_id)
        if not run:
            return {"error": "not_found"}
        path = run.get("result_path")
        detail: Dict[str, Any] = {}
        if path:
            try:
                from pathlib import Path

                detail = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                detail = {}
        return {"run": run, "detail": detail}

    @app.post("/api/jobs/validate")
    def job_validate(body: ValidateBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="仔细验策略",
            job_type="validate",
            env="quant",
            params={
                "from_run_id": body.from_run,
                "strategy_id": body.strategy,
                "short_window": body.short,
                "long_window": body.long,
                "match_price": body.match,
                "benchmark": body.benchmark,
                "screen_run_id": body.screen_run_id,
            },
        )
        return {"job_id": job_id}

    @app.get("/api/validate/{run_id}")
    def api_validate(run_id: str) -> Dict[str, Any]:
        with db_session() as conn:
            run = get_backtest_run(conn, run_id)
        if not run:
            return {"error": "not_found"}
        path = run.get("result_path")
        detail: Dict[str, Any] = {}
        if path:
            try:
                from pathlib import Path

                detail = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                detail = {}
        return {"run": run, "detail": detail}

    @app.post("/api/jobs/screen")
    def job_screen(body: ScreenBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="选股",
            job_type="screen",
            env="quant",
            params={
                "template_id": body.template,
                "top_n": body.top,
                "sector": body.sector,
                "exclude_st": body.exclude_st,
                "pe_max": body.pe_max,
                "roe_min": body.roe_min,
                "rule_path": body.rule_path,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/screen/ic")
    def job_screen_ic(body: ScreenIcBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="因子 IC 分析",
            job_type="screen_ic",
            env="quant",
            params={"template_id": body.template, "sector": body.sector},
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/screen/backtest")
    def job_screen_backtest(body: ScreenBacktestBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="选股回测",
            job_type="screen_backtest",
            env="quant",
            params={
                "run_id": body.run_id,
                "engine": body.engine,
                "range_preset": body.range_preset,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/pipeline")
    def job_pipeline() -> Dict[str, str]:
        job_id = submit_job(
            display_name="一键跑通",
            job_type="pipeline",
            env="quant",
            params={},
        )
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str) -> Dict[str, Any]:
        job = fetch_job(job_id)
        return job or {"error": "not_found"}

    @app.post("/api/jobs/{job_id}/retry")
    def api_job_retry(job_id: str) -> Dict[str, str]:
        job = fetch_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="not_found")
        new_id = submit_job(
            display_name=job.get("display_name", "重试任务"),
            job_type=job.get("job_type", ""),
            env=job.get("env", "quant"),
            params=job.get("params_json") or {},
        )
        return {"job_id": new_id}

    @app.get("/api/jobs")
    def api_jobs(limit: int = 20) -> List[Dict[str, Any]]:
        return list_recent_jobs(limit)

    @app.get("/api/options/sectors")
    def options_sectors() -> List[Dict[str, str]]:
        return [
            {"id": "沪深A股", "label": "沪深A股"},
            {"id": "沪深300", "label": "沪深300"},
            {"id": "中证500", "label": "中证500"},
            {"id": "watchlist", "label": "我的自选池"},
        ]

    @app.get("/api/options/strategies")
    def options_strategies() -> List[Dict[str, str]]:
        return [
            {"id": "ma_cross", "label": "双均线"},
            {"id": "buy_hold", "label": "买入持有基准"},
            {"id": "pe_momentum", "label": "低估值 + 动量"},
            {"id": "screening_rebalance", "label": "选股调仓"},
        ]

    @app.get("/api/options/ranges")
    def options_ranges() -> List[Dict[str, str]]:
        return [{"id": k, "label": v["label"]} for k, v in RANGE_PRESETS.items()]

    @app.get("/api/options/ma-presets")
    def options_ma() -> Dict[str, List[Dict[str, str]]]:
        return {
            "short": [{"id": k, "label": v["label"]} for k, v in SHORT_MA_PRESETS.items()],
            "long": [{"id": k, "label": v["label"]} for k, v in LONG_MA_PRESETS.items()],
        }

    @app.get("/api/options/fees")
    def options_fees() -> List[Dict[str, str]]:
        return [{"id": k, "label": v["label"]} for k, v in FEE_PRESETS.items()]

    @app.get("/api/options/templates")
    def options_templates() -> List[Dict[str, str]]:
        return [{"id": k, "label": v.name} for k, v in TEMPLATES.items()]

    @app.get("/api/options/research-runs")
    def options_research_runs() -> List[Dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT id, title, metrics_json, created_at FROM backtest_run WHERE engine='vectorbt' ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        out = []
        for row in rows:
            metrics = json.loads(row[2]) if row[2] else {}
            out.append(
                {
                    "id": row[0],
                    "label": f"{row[1]} ({metrics.get('label', '')})",
                    "created_at": row[3],
                }
            )
        return out

    @app.get("/api/options/validate-runs")
    def options_validate_runs() -> List[Dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT id, title, metrics_json, created_at, engine
                FROM backtest_run
                WHERE engine IN ('custom_validator', 'nautilus')
                ORDER BY created_at DESC LIMIT 30
                """
            ).fetchall()
        out = []
        for row in rows:
            metrics = json.loads(row[2]) if row[2] else {}
            out.append(
                {
                    "id": row[0],
                    "label": f"[{row[4]}] {row[1]} ({metrics.get('verdict', '')})",
                    "created_at": row[3],
                    "engine": row[4],
                }
            )
        return out

    @app.get("/api/options/screening-runs")
    def options_screening_runs() -> List[Dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT run_id, MAX(as_of_date) AS as_of, COUNT(*) AS cnt, MAX(reason) AS reason
                FROM screening_result
                GROUP BY run_id
                ORDER BY MAX(created_at) DESC
                LIMIT 30
                """
            ).fetchall()
        return [
            {"id": r[0], "label": f"{r[3] or '选股'} {r[1]} ({r[2]}只)"}
            for r in rows
        ]

    @app.get("/api/screening/{run_id}/codes")
    def screening_codes(run_id: str) -> Dict[str, List[str]]:
        from qmt_quant.core.screener.bridge import load_codes_by_run_id

        return {"codes": load_codes_by_run_id(run_id)}

    @app.get("/api/settings")
    def api_get_settings() -> Dict[str, Any]:
        s = get_settings()
        return s.to_dict()

    @app.put("/api/settings")
    def api_put_settings(body: SettingsBody) -> Dict[str, Any]:
        s = get_settings()
        if body.qmt_install_dir is not None:
            s.qmt_install_dir = body.qmt_install_dir
        if body.qmt_python is not None:
            s.qmt_python = body.qmt_python
        if body.quant_python is not None:
            s.quant_python = body.quant_python
        if body.userdata_path is not None:
            s.userdata_path = body.userdata_path
        if body.account_id is not None:
            s.account_id = body.account_id
        if body.dry_run is not None:
            s.dry_run = body.dry_run
        if body.commission_rate is not None:
            s.commission_rate = body.commission_rate
        if body.stamp_tax_rate is not None:
            s.stamp_tax_rate = body.stamp_tax_rate
        if body.sync_auto_repair is not None:
            s.sync_auto_repair = body.sync_auto_repair
        s.save()
        from qmt_quant import config

        config._settings = None
        return get_settings().to_dict()

    @app.get("/api/trade/status")
    def api_trade_status() -> Dict[str, Any]:
        return get_trade_status()

    @app.post("/api/trade/preview")
    def api_trade_preview(body: TradeBody) -> List[Dict[str, Any]]:
        return preview_signal_orders(body.codes, body.side, body.quantity)

    @app.post("/api/trade/submit")
    def api_trade_submit(body: TradeBody) -> List[Dict[str, Any]]:
        if body.live and body.confirm != "LIVE":
            return [{"error": "live orders require confirm=LIVE"}]
        orders = preview_signal_orders(body.codes, body.side, body.quantity)
        return submit_orders(orders, live=body.live)

    @app.websocket("/ws/jobs")
    async def ws_jobs(websocket: WebSocket) -> None:
        await websocket.accept()
        job_manager.connections.add(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            job_manager.connections.discard(websocket)

    return app
