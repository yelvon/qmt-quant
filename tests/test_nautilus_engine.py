"""Nautilus validation engine tests."""

import pandas as pd
import pytest


def test_nautilus_fallback_without_package():
    from qmt_quant.core.validation.nautilus_runner import run_nautilus_validation

    idx = pd.date_range("2023-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"600519.SH": 100 + pd.Series(range(200)).values * 0.05}, index=idx)
    result = run_nautilus_validation(strategy_id="ma_cross", prices=prices, short_window=5, long_window=20)
    assert result.total_return_pct is not None


def test_validation_engine_label():
    from qmt_quant.core.validation.engine import validation_engine_label

    assert validation_engine_label("custom") == "custom_validator"
    assert validation_engine_label("nautilus") == "nautilus"


@pytest.mark.skipif(
    pytest.importorskip("nautilus_trader", reason="nautilus not installed") is None,
    reason="nautilus",
)
def test_nautilus_engine_smoke():
    pytest.importorskip("nautilus_trader")
    from qmt_quant.core.validation.engine import NautilusValidationEngine

    idx = pd.date_range("2023-01-01", periods=260, freq="B")
    prices = pd.DataFrame({"600519.SH": 100 + pd.Series(range(260)).values * 0.02}, index=idx)
    engine = NautilusValidationEngine()
    result = engine.run("ma_cross", prices, short_window=10, long_window=30)
    assert hasattr(result, "total_return_pct")
