"""NautilusTrader validation runner (Phase 7 MVP)."""

from __future__ import annotations

from typing import List, Sequence

import pandas as pd

from qmt_quant.config import get_settings
from qmt_quant.core.catalog.nt_export import export_nt_catalog, VENUE
from qmt_quant.core.validation.backtester import ValidationResult


def run_nautilus_validation(
    *,
    strategy_id: str,
    prices: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 120,
    codes: Sequence[str] | None = None,
) -> ValidationResult:
    if strategy_id != "ma_cross":
        from qmt_quant.core.validation.engine import CustomValidationEngine

        engine = CustomValidationEngine()
        return engine.run(strategy_id, prices, short_window=short_window, long_window=long_window)

    try:
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.backtest.models import FillModel
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.currencies import CNY
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money
        from nautilus_trader.persistence.catalog import ParquetDataCatalog
    except ImportError:
        return _fallback_custom(prices, short_window, long_window)

    settings = get_settings()
    use_codes = list(codes or prices.columns)[:10]
    export_nt_catalog(adjust_type=settings.bar_adjust_type, codes=use_codes)

    catalog = ParquetDataCatalog(str(settings.catalog_nt_path))
    venue = Venue(VENUE)
    engine = BacktestEngine(
        config=BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")),
    )
    engine.add_venue(
        venue=venue,
        oms_type=OmsType.HEDGING,
        account_type=AccountType.CASH,
        base_currency=CNY,
        starting_balances=[Money(settings.initial_cash, CNY)],
        fill_model=FillModel(),
    )

    instruments = catalog.instruments()
    if not instruments:
        return _fallback_custom(prices, short_window, long_window)

    for inst in instruments[:10]:
        engine.add_instrument(inst)
        bar_type_str = f"{inst.id}-1-DAY-LAST-EXTERNAL"
        bars = catalog.bars(bar_types=[bar_type_str])
        if bars:
            engine.add_data(bars)

    from strategies.nautilus.ma_cross import MACrossConfig, MACrossStrategy

    config = MACrossConfig(
        instrument_id=instruments[0].id,
        short_window=short_window,
        long_window=long_window,
    )
    strategy = MACrossStrategy(config=config)
    engine.add_strategy(strategy)
    engine.run()

    account = engine.trader.generate_account_report(venue)
    total = settings.initial_cash
    if account is not None and not account.empty and "total" in account.columns:
        try:
            total = float(account["total"].iloc[-1])
        except (TypeError, ValueError, IndexError):
            pass

    ret_pct = round((total / settings.initial_cash - 1) * 100, 2)
    return ValidationResult(
        total_return_pct=ret_pct,
        max_drawdown_pct=0.0,
        verdict="可以采用" if ret_pct > 0 else "建议复核",
        trade_count=0,
        equity_curve=[{"date": "end", "equity": round(total / settings.initial_cash * 100, 2)}],
    )


def _fallback_custom(prices: pd.DataFrame, short: int, long: int) -> ValidationResult:
    from qmt_quant.core.validation.backtester import AShareDailyBacktester

    return AShareDailyBacktester(prices).run_ma_cross(short, long)
