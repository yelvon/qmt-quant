"""API smoke tests (no QMT required)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "doctor_ok" in data
    assert "suggestion" in data
    assert "actions" in data
    assert isinstance(data["actions"], list)
    assert "onboarding_complete" in data
    assert isinstance(data.get("has_strategy_run"), bool)


def test_doctor(client):
    res = client.get("/api/doctor")
    assert res.status_code == 200
    assert "checks" in res.json()


def test_options(client):
    res = client.get("/api/options/strategies")
    assert res.status_code == 200
    assert any(o["id"] == "ma_cross" for o in res.json())
    assert any(o["id"] == "macd_cross" for o in res.json())


def test_data_meta(client):
    res = client.get("/api/data/meta?table=daily_bar")
    assert res.status_code == 200
    data = res.json()
    assert data["table"] == "daily_bar"
    assert "columns" in data
    assert "adjust_options" in data


def test_index_data_meta_and_query(client, db):
    from qmt_quant.storage.database import db_session
    from qmt_quant.storage.index_bars import IndexBarRow, upsert_index_bars, upsert_index_instruments

    with db_session(db) as conn:
        upsert_index_instruments(conn, [("000300.SH", "沪深300", "benchmark", None)])
        upsert_index_bars(
            conn,
            [
                IndexBarRow(
                    code="000300.SH",
                    date="2024-01-02",
                    open=1,
                    high=2,
                    low=1,
                    close=1.5,
                    volume=1,
                    amount=1,
                    pre_close=1,
                )
            ],
        )
    meta = client.get("/api/data/meta?table=index_daily_bar")
    assert meta.status_code == 200
    assert meta.json()["table"] == "index_daily_bar"
    assert meta.json()["adjust_options"] == []
    res = client.get(
        "/api/data/query?table=index_daily_bar&view_mode=cross_section&date=2024-01-02"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["rows"][0]["kind"] == "基准"
    assert data["rows"][0]["name"] == "沪深300"
    inst = client.get("/api/data/index-instruments")
    assert inst.status_code == 200
    assert any(i["code"] == "000300.SH" for i in inst.json()["items"])
    kline = client.get("/api/data/kline?code=000300.SH&adjust=front")
    assert kline.status_code == 200
    assert kline.json()["adjust"] == "none"
    dates = client.get("/api/data/dates?table=index_daily_bar")
    assert dates.status_code == 200
    assert dates.json()["min_date"] == "2024-01-02"


def test_data_query_missing_date(client):
    res = client.get("/api/data/query?table=daily_bar&view_mode=cross_section")
    assert res.status_code == 400


def test_data_query_cross_section(client, db):
    from qmt_quant.storage.bars import BarRow, upsert_bars
    from qmt_quant.storage.database import db_session

    with db_session(db) as conn:
        upsert_bars(
            conn,
            [
                BarRow(
                    code="600519.SH",
                    date="2024-01-02",
                    adjust_type="front",
                    open=1,
                    high=2,
                    low=1,
                    close=1.5,
                    volume=1,
                    amount=1,
                )
            ],
        )
    res = client.get(
        "/api/data/query?table=daily_bar&view_mode=cross_section&date=2024-01-02&adjust=front"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["rows"][0]["code"] == "600519.SH"


def test_data_kline(client, db):
    from qmt_quant.storage.bars import BarRow, upsert_bars
    from qmt_quant.storage.database import db_session

    with db_session(db) as conn:
        upsert_bars(
            conn,
            [
                BarRow(
                    code="600519.SH",
                    date="2024-01-02",
                    adjust_type="front",
                    open=10,
                    high=11,
                    low=9,
                    close=10.5,
                    volume=100,
                    amount=1050,
                )
            ],
        )
    res = client.get("/api/data/kline?code=600519.SH&adjust=front")
    assert res.status_code == 200
    data = res.json()
    assert data["empty"] is False
    assert data["ohlc"][0] == [10, 10.5, 9, 11]


def test_data_dates(client):
    res = client.get("/api/data/dates?adjust=front")
    assert res.status_code == 200
    assert "min_date" in res.json()


def test_research_universe_endpoint(client, monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(80)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    res = client.get("/api/options/research-universe?sector=沪深A股&strategy=ma_cross")
    assert res.status_code == 200
    data = res.json()
    assert data["pool_size"] == 80
    assert data["used"] == 50
    assert data["capped"] is True
    assert data["cap"] == 50


def test_validation_engines_endpoint(client):
    res = client.get("/api/options/validation-engines")
    assert res.status_code == 200
    data = res.json()
    assert data["current"]
    assert any(o["id"] == "custom" for o in data["options"])


def test_screen_invalid_yaml(client):
    res = client.post("/api/jobs/screen", json={"rule_yaml": "- just a list"})
    assert res.status_code == 400


def test_trade_live_requires_confirm(client):
    res = client.post(
        "/api/trade/submit",
        json={"codes": ["600519.SH"], "live": True},
    )
    assert res.status_code == 403
