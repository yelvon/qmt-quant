import pytest

from qmt_quant.storage.bars import BarRow, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    yield db_file
    config._settings = None


def test_bar_upsert_idempotent(db):
    rows = [
        BarRow(
            code="600519.SH",
            date="2024-01-02",
            adjust_type="front",
            open=10.0,
            high=11.0,
            low=9.5,
            close=10.5,
            volume=1000,
            amount=10500,
        )
    ]
    with db_session(db) as conn:
        upsert_bars(conn, rows)
        upsert_bars(conn, rows)
        count = conn.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0]
    assert count == 1


def test_bar_update_on_conflict(db):
    with db_session(db) as conn:
        upsert_bars(
            conn,
            [
                BarRow(
                    code="000001.SZ",
                    date="2024-01-03",
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
        upsert_bars(
            conn,
            [
                BarRow(
                    code="000001.SZ",
                    date="2024-01-03",
                    adjust_type="front",
                    open=1,
                    high=2,
                    low=1,
                    close=2.0,
                    volume=2,
                    amount=2,
                )
            ],
        )
        close = conn.execute(
            "SELECT close FROM daily_bar WHERE code=? AND date=?",
            ("000001.SZ", "2024-01-03"),
        ).fetchone()[0]
    assert close == 2.0
