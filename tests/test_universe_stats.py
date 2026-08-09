"""Universe stats tests."""

from qmt_quant.core.sync.universe_stats import (
    record_universe_count,
    resolve_universe_total,
)
from qmt_quant.storage.database import db_session, run_migrations


def test_resolve_universe_total_uses_cache(tmp_path, monkeypatch):
    db_file = tmp_path / "u.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    with db_session(db_file) as conn:
        record_universe_count(conn, "沪深A股", 5207)
        total, estimated = resolve_universe_total(conn, "沪深A股", bar_codes=3)
    assert total == 5207
    assert estimated is False
    config._settings = None


def test_resolve_universe_total_estimated_when_unknown(tmp_path, monkeypatch):
    db_file = tmp_path / "u2.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    with db_session(db_file) as conn:
        conn.execute("INSERT INTO instrument(code) VALUES ('A'), ('B')")
        total, estimated = resolve_universe_total(conn, "沪深A股", bar_codes=3)
    assert estimated is True
    assert total >= 3
    config._settings = None
