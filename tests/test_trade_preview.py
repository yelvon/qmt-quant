"""Trade preview / submit API tests (no xttrader)."""

from qmt_quant.core.trade.service import flatten_trade_orders, preview_signal_orders


def test_flatten_orders_prefers_explicit_list():
    out = flatten_trade_orders(
        codes=["600519.SH"],
        side="buy",
        quantity=100,
        orders=[{"code": "000001.SZ", "side": "sell", "quantity": 200}],
    )
    assert out == [{"code": "000001.SZ", "side": "sell", "quantity": 200}]


def test_flatten_orders_legacy_codes():
    out = flatten_trade_orders(codes=["600519.SH"], side="buy", quantity=100)
    assert out == [{"code": "600519.SH", "side": "buy", "quantity": 100}]


def test_preview_rejects_odd_lot(monkeypatch):
    monkeypatch.setattr("qmt_quant.core.trade.service._is_st_code", lambda code: False)

    class _Trader:
        connected = True

        def connect(self):
            return True

        def portfolio_value(self):
            return 1_000_000

    monkeypatch.setattr("qmt_quant.core.trade.service.QmtTrader", _Trader)
    rows = preview_signal_orders(["600519.SH"], quantity=150)
    assert rows[0]["ok"] is False


def test_preview_rejects_st(monkeypatch):
    monkeypatch.setattr("qmt_quant.core.trade.service._is_st_code", lambda code: True)

    class _Trader:
        connected = True

        def connect(self):
            return True

        def portfolio_value(self):
            return 1_000_000

    monkeypatch.setattr("qmt_quant.core.trade.service.QmtTrader", _Trader)
    rows = preview_signal_orders(["600001.SH"], quantity=100)
    assert rows[0]["ok"] is False
    assert "ST" in rows[0]["reason"]


def test_preview_allows_sell(monkeypatch):
    monkeypatch.setattr("qmt_quant.core.trade.service._is_st_code", lambda code: False)

    class _Trader:
        connected = True

        def connect(self):
            return True

        def portfolio_value(self):
            return 1_000_000

    monkeypatch.setattr("qmt_quant.core.trade.service.QmtTrader", _Trader)
    rows = preview_signal_orders(orders=[{"code": "600519.SH", "side": "sell", "quantity": 200}])
    assert rows[0]["ok"] is True
    assert rows[0]["side"] == "sell"
