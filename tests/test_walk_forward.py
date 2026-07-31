"""Walk-forward analysis tests."""

import pandas as pd

from qmt_quant.core.research.walk_forward import run_walk_forward


def test_walk_forward_segments_no_lookahead():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    prices = pd.DataFrame({"A": 100 + pd.Series(range(400)).values * 0.1}, index=idx)

    result = run_walk_forward(
        prices,
        train_bars=120,
        test_bars=40,
        step_bars=40,
    )
    assert result["segment_count"] >= 1
    segments = result["segments"]
    for seg in segments:
        assert seg["train_end"] < seg["test_start"]
        assert seg["short"] > 0
        assert seg["long"] > seg["short"]


def test_walk_forward_insufficient_data():
    prices = pd.DataFrame({"A": [1, 2, 3]})
    result = run_walk_forward(prices, train_bars=252, test_bars=63)
    assert result.get("error") == "insufficient_data"
