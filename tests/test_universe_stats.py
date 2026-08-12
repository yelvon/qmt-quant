"""Universe stats tests."""

from qmt_quant.core.sync.universe_stats import (
    record_universe_count,
    resolve_universe_total,
)
from qmt_quant.storage.database import db_session


def test_resolve_universe_total_uses_cache(db):
    with db_session(db) as conn:
        record_universe_count(conn, "沪深A股", 5207)
        total, estimated = resolve_universe_total(conn, "沪深A股", bar_codes=3)
    assert total == 5207
    assert estimated is False


def test_resolve_universe_total_estimated_when_unknown(db):
    with db_session(db) as conn:
        conn.execute("INSERT INTO instrument(code) VALUES ('A'), ('B')")
        total, estimated = resolve_universe_total(conn, "测试板块_未知", bar_codes=3)
    assert estimated is True
    assert total >= 3
