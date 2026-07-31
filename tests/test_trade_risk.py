"""Trade risk tests."""

from qmt_quant.core.trade.risk import check_order, filter_allowed


def test_reject_st():
    ok, msg = check_order(
        code="600001.SH",
        side="buy",
        quantity=100,
        portfolio_value=1_000_000,
        order_value=10_000,
        is_st=True,
    )
    assert not ok
    assert "ST" in msg


def test_reject_odd_lot():
    ok, msg = check_order(
        code="600519.SH",
        side="buy",
        quantity=150,
        portfolio_value=1_000_000,
        order_value=10_000,
    )
    assert not ok


def test_filter_allowed():
    assert filter_allowed(["A", "B"], ["B"]) == ["A"]
