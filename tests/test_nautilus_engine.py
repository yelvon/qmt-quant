"""Nautilus validation engine tests."""

import pandas as pd
import pytest


def test_nautilus_never_silently_falls_back(monkeypatch):
    from qmt_quant.core.validation.nautilus_runner import run_nautilus_validation

    idx = pd.date_range("2023-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"600519.SH": 100 + pd.Series(range(200)).values * 0.05}, index=idx)
    with pytest.raises(ValueError, match="实验引擎暂不支持"):
        run_nautilus_validation(
            strategy_id="unsupported",
            prices=prices,
            short_window=5,
            long_window=20,
        )


def test_validation_engine_label():
    from qmt_quant.core.validation.engine import validation_engine_label

    assert validation_engine_label("custom") == "custom_validator"
    assert validation_engine_label("nautilus") == "nautilus"


def test_get_validation_engine_none_uses_settings(monkeypatch):
    from qmt_quant.core.validation import engine as eng

    class _S:
        validation_engine = "custom"

    monkeypatch.setattr(eng, "get_settings", lambda: _S())
    got = eng.get_validation_engine(None)
    assert isinstance(got, eng.CustomValidationEngine)


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
