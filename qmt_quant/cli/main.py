"""CLI entrypoint."""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from qmt_quant.core.doctor import run_doctor
from qmt_quant.storage.database import run_migrations

app = typer.Typer(help="qmt-quant CLI", no_args_is_help=True)
sync_app = typer.Typer(help="Data sync commands")
catalog_app = typer.Typer(help="Catalog export")
research_app = typer.Typer(help="VectorBT research")
validate_app = typer.Typer(help="Nautilus validation")
screen_app = typer.Typer(help="Stock screening")
trade_app = typer.Typer(help="Live trading")
serve_app = typer.Typer(help="Web server")

app.add_typer(sync_app, name="sync")
app.add_typer(catalog_app, name="catalog")
app.add_typer(research_app, name="research")
app.add_typer(validate_app, name="validate")
app.add_typer(screen_app, name="screen")
app.add_typer(trade_app, name="trade")
app.add_typer(serve_app, name="serve")


@app.command("doctor")
def doctor_cmd() -> None:
    """Check environment, QMT path, and writable data directories."""
    report = run_doctor()
    for check in report.checks:
        mark = "OK" if check.ok else "FAIL"
        typer.echo(f"[{mark}] {check.name}: {check.message}")
    if not report.ok:
        raise typer.Exit(code=1)


@app.command("init-db")
def init_db_cmd() -> None:
    """Run database migrations."""
    run_migrations()
    typer.echo("Database migrations applied.")


@sync_app.command("universe")
def sync_universe(sector: str = typer.Option("沪深A股", help="QMT sector name")) -> None:
    from qmt_quant.core.sync.universe import sync_universe as _sync

    count = _sync(sector)
    typer.echo(f"Synced universe: {count} instruments")


@sync_app.command("bars")
def sync_bars(
    start: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD"),
    adjust: str = typer.Option("front", help="none|front|back"),
    incremental: bool = typer.Option(False, help="Incremental sync"),
    days: int = typer.Option(5, help="Incremental lookback days"),
    sector: str = typer.Option("沪深A股"),
) -> None:
    from qmt_quant.core.sync.bars import sync_bars as _sync

    stats = _sync(
        sector=sector,
        start_date=start,
        adjust_type=adjust,
        incremental=incremental,
        incremental_days=days,
    )
    typer.echo(json.dumps(stats, ensure_ascii=False, indent=2))


@sync_app.command("financial")
def sync_financial(
    tables: str = typer.Option(
        "Balance,Income,CashFlow,Pershareindex",
        help="Comma-separated table names",
    ),
    sector: str = typer.Option("沪深A股"),
) -> None:
    from qmt_quant.core.sync.financial import sync_financial as _sync

    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    stats = _sync(sector=sector, tables=table_list)
    typer.echo(json.dumps(stats, ensure_ascii=False, indent=2))


@sync_app.command("calendar")
def sync_calendar_cmd() -> None:
    from qmt_quant.core.sync.calendar import sync_calendar_from_bars

    count = sync_calendar_from_bars()
    typer.echo(f"Synced trade calendar from bars: {count} dates")


@sync_app.command("check")
def sync_check(
    date: Optional[str] = typer.Option(None, help="As-of date YYYY-MM-DD"),
    adjust: str = typer.Option("front"),
) -> None:
    from qmt_quant.core.sync.check import run_data_check

    result = run_data_check(as_of_date=date, adjust_type=adjust)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@catalog_app.command("export")
def catalog_export(adjust: str = typer.Option("front")) -> None:
    from qmt_quant.core.catalog.export import export_catalog

    stats = export_catalog(adjust_type=adjust)
    typer.echo(json.dumps(stats, ensure_ascii=False, indent=2))


@research_app.command("run")
def research_run(
    strategy: str = typer.Option("ma_cross"),
    sector: str = typer.Option("沪深A股"),
    range_preset: str = typer.Option("3y", help="1y|3y|5y|all"),
    short_preset: str = typer.Option("preset_std"),
    long_preset: str = typer.Option("preset_std"),
    fee_preset: str = typer.Option("default"),
) -> None:
    from qmt_quant.core.research.runner import run_research

    result = run_research(
        strategy_id=strategy,
        sector=sector,
        range_preset=range_preset,
        short_preset=short_preset,
        long_preset=long_preset,
        fee_preset=fee_preset,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@validate_app.command("run")
def validate_run(
    from_run: Optional[str] = typer.Option(None, help="Research run id"),
    strategy: str = typer.Option("ma_cross"),
    short: int = typer.Option(20),
    long: int = typer.Option(120),
    match: str = typer.Option("next_open"),
    benchmark: str = typer.Option("hs300"),
) -> None:
    from qmt_quant.core.validation.runner import run_validation

    result = run_validation(
        from_run_id=from_run,
        strategy_id=strategy,
        short_window=short,
        long_window=long,
        match_price=match,
        benchmark=benchmark,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@screen_app.command("run")
def screen_run(
    template: str = typer.Option("low_pe"),
    top: int = typer.Option(30),
    sector: str = typer.Option("沪深A股"),
    exclude_st: bool = typer.Option(True),
) -> None:
    from qmt_quant.core.screener.runner import run_screening

    result = run_screening(
        template_id=template,
        top_n=top,
        sector=sector,
        exclude_st=exclude_st,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@trade_app.command("status")
def trade_status() -> None:
    from qmt_quant.core.trade.service import get_trade_status

    typer.echo(json.dumps(get_trade_status(), ensure_ascii=False, indent=2))


@serve_app.command("api")
def serve_api(
    host: Optional[str] = None,
    port: Optional[int] = None,
    reload: bool = typer.Option(False),
) -> None:
    import uvicorn

    from qmt_quant.config import get_settings
    from qmt_quant.web.app import create_app

    settings = get_settings()
    uvicorn.run(
        create_app(),
        host=host or settings.web_host,
        port=port or settings.web_port,
        reload=reload,
    )


@app.command("pipeline")
def pipeline_cmd(
    strategy: str = typer.Option("ma_cross"),
    range_preset: str = typer.Option("3y"),
    days: int = typer.Option(5),
) -> None:
    """Run sync → research → validate in one shot."""
    from qmt_quant.core.jobs.runner import run_pipeline

    result = run_pipeline({"strategy": strategy, "range_preset": range_preset, "days": days})
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
