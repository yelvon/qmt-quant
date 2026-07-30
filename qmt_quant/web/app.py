"""FastAPI application for qmt-quant web UI."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from qmt_quant.config import get_settings
from qmt_quant.core.doctor import run_doctor
from qmt_quant.core.jobs.runner import fetch_job, list_recent_jobs, submit_job, subscribe
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


class SyncBarsBody(BaseModel):
    sector: str = "沪深A股"
    incremental: bool = True
    days: int = 5
    adjust: str = "front"


class SyncFinancialBody(BaseModel):
    sector: str = "沪深A股"
    tables: List[str] = Field(default_factory=lambda: ["Balance", "Income", "CashFlow", "Pershareindex"])


class ResearchBody(BaseModel):
    strategy: str = "ma_cross"
    sector: str = "沪深A股"
    range_preset: str = "3y"
    short_preset: str = "preset_std"
    long_preset: str = "preset_std"
    fee_preset: str = "default"


class ValidateBody(BaseModel):
    from_run: Optional[str] = None
    strategy: str = "ma_cross"
    short: int = 20
    long: int = 120
    match: str = "next_open"


class ScreenBody(BaseModel):
    template: str = "low_pe"
    top: int = 30
    sector: str = "沪深A股"
    exclude_st: bool = True


class TradeBody(BaseModel):
    codes: List[str]
    side: str = "buy"
    quantity: int = 100
    live: bool = False


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
        suggestion = "更新今日数据"
        if check.get("bar_coverage_pct", 0) > 80:
            suggestion = "快速试策略"
        return {
            "doctor_ok": doctor.ok,
            "checks": [c.__dict__ for c in doctor.checks],
            "data_check": check,
            "recent_jobs": jobs,
            "suggestion": suggestion,
        }

    @app.get("/api/data/check")
    def api_data_check() -> Dict[str, Any]:
        return run_data_check()

    @app.post("/api/jobs/sync/bars")
    def job_sync_bars(body: SyncBarsBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="更新行情",
            job_type="sync_bars",
            env="qmt",
            params={
                "sector": body.sector,
                "incremental": body.incremental,
                "incremental_days": body.days,
                "adjust_type": body.adjust,
            },
        )
        return {"job_id": job_id}

    @app.post("/api/jobs/sync/financial")
    def job_sync_financial(body: SyncFinancialBody) -> Dict[str, str]:
        job_id = submit_job(
            display_name="同步财报",
            job_type="sync_financial",
            env="qmt",
            params={"sector": body.sector, "tables": body.tables},
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

    @app.get("/api/jobs")
    def api_jobs(limit: int = 20) -> List[Dict[str, Any]]:
        return list_recent_jobs(limit)

    @app.get("/api/options/sectors")
    def options_sectors() -> List[Dict[str, str]]:
        return [
            {"id": "沪深A股", "label": "沪深A股"},
            {"id": "watchlist", "label": "我的自选池"},
        ]

    @app.get("/api/options/strategies")
    def options_strategies() -> List[Dict[str, str]]:
        return [
            {"id": "ma_cross", "label": "双均线"},
            {"id": "buy_hold", "label": "买入持有基准"},
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

    @app.get("/api/trade/status")
    def api_trade_status() -> Dict[str, Any]:
        return get_trade_status()

    @app.post("/api/trade/preview")
    def api_trade_preview(body: TradeBody) -> List[Dict[str, Any]]:
        return preview_signal_orders(body.codes, body.side, body.quantity)

    @app.post("/api/trade/submit")
    def api_trade_submit(body: TradeBody) -> List[Dict[str, Any]]:
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
