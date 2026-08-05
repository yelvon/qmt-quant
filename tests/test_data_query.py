"""Tests for data browse query layer."""

import pytest

from qmt_quant.core.data.query import get_date_range, query_table
from qmt_quant.storage.bars import BarRow, upsert_bars
from qmt_quant.storage.database import db_session, run_migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "query.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)
    with db_session(db_file) as conn:
        conn.execute(
            """
            INSERT INTO instrument(code, name, list_date, is_st)
            VALUES ('600519.SH', '贵州茅台', '2001-08-27', 0),
                   ('000001.SZ', '平安银行', '1991-04-03', 0)
            """
        )
        upsert_bars(
            conn,
            [
                BarRow(
                    code="600519.SH",
                    date="2024-01-02",
                    adjust_type="front",
                    open=100,
                    high=105,
                    low=99,
                    close=104,
                    volume=1000,
                    amount=104000,
                    pre_close=100,
                ),
                BarRow(
                    code="600519.SH",
                    date="2024-01-03",
                    adjust_type="front",
                    open=104,
                    high=106,
                    low=103,
                    close=105,
                    volume=900,
                    amount=94500,
                    pre_close=104,
                ),
                BarRow(
                    code="000001.SZ",
                    date="2024-01-02",
                    adjust_type="front",
                    open=10,
                    high=10.5,
                    low=9.8,
                    close=10.2,
                    volume=5000,
                    amount=51000,
                    pre_close=10,
                ),
            ],
        )
    yield db_file
    config._settings = None


def test_cross_section_requires_date(db):
    with db_session(db) as conn:
        with pytest.raises(ValueError, match="missing_date"):
            query_table(conn, "daily_bar", "cross_section", adjust_type="front")


def test_cross_section_pagination(db):
    with db_session(db) as conn:
        result = query_table(
            conn,
            "daily_bar",
            "cross_section",
            date="2024-01-02",
            adjust_type="front",
            page=1,
            page_size=10,
            sort_col="code",
            sort_dir="asc",
        )
    assert result["total"] == 2
    assert len(result["rows"]) == 2
    codes = {r["code"] for r in result["rows"]}
    assert codes == {"600519.SH", "000001.SZ"}
    moutai = next(r for r in result["rows"] if r["code"] == "600519.SH")
    assert moutai["name"] == "贵州茅台"
    assert moutai["change_pct"] == pytest.approx(4.0)


def test_series_requires_code(db):
    with db_session(db) as conn:
        with pytest.raises(ValueError, match="missing_code"):
            query_table(conn, "daily_bar", "series", adjust_type="front")


def test_series_date_range(db):
    with db_session(db) as conn:
        result = query_table(
            conn,
            "daily_bar",
            "series",
            code="600519",
            date_from="2024-01-02",
            date_to="2024-01-03",
            adjust_type="front",
            sort_col="date",
            sort_dir="asc",
        )
    assert result["total"] == 2
    assert result["rows"][0]["date"] == "2024-01-02"
    assert result["rows"][1]["date"] == "2024-01-03"


def test_instrument_list_search(db):
    with db_session(db) as conn:
        result = query_table(
            conn,
            "instrument",
            "instrument_list",
            q="茅台",
            sort_col="code",
        )
    assert result["total"] == 1
    assert result["rows"][0]["code"] == "600519.SH"


def test_invalid_sort_col(db):
    with db_session(db) as conn:
        with pytest.raises(ValueError, match="invalid_sort_col"):
            query_table(
                conn,
                "daily_bar",
                "cross_section",
                date="2024-01-02",
                sort_col="; DROP TABLE",
            )


def test_date_range(db):
    with db_session(db) as conn:
        dr = get_date_range(conn, "front")
    assert dr["min_date"] == "2024-01-02"
    assert dr["max_date"] == "2024-01-03"
