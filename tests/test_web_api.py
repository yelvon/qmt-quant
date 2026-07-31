"""API smoke tests (no QMT required)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from qmt_quant.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "api.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    app = create_app()
    yield TestClient(app)
    config._settings = None


def test_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "doctor_ok" in data
    assert "suggestion" in data
    assert "actions" in data
    assert isinstance(data["actions"], list)
    assert "onboarding_complete" in data


def test_doctor(client):
    res = client.get("/api/doctor")
    assert res.status_code == 200
    assert "checks" in res.json()


def test_options(client):
    res = client.get("/api/options/strategies")
    assert res.status_code == 200
    assert any(o["id"] == "ma_cross" for o in res.json())
