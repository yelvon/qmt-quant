"""Index catalog, window rules, and isolated index_daily_bar sync."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from qmt_quant.core.presets import resolve_range_preset
from qmt_quant.core.sync.indices import (
    filter_industry_codes,
    index_sync_window,
    looks_like_index_code,
    pick_industry_sector,
)
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.core.data.kline import build_kline_payload
from qmt_quant.core.data.query import query_table
from qmt_quant.storage.database import db_session
from qmt_quant.storage.index_bars import IndexBarRow, upsert_index_bars, upsert_index_instruments


def test_looks_like_index_code_keeps_benchmarks_rejects_stocks():
    assert looks_like_index_code("000001.SH")
    assert looks_like_index_code("000300.SH")
    assert looks_like_index_code("399001.SZ")
    assert looks_like_index_code("801010.SI")
    assert not looks_like_index_code("000001.SZ")
    assert not looks_like_index_code("600519.SH")
    assert not looks_like_index_code("300750.SZ")


def test_filter_industry_codes_drops_constituents():
    codes = [
        "600000.SH",
        "000001.SZ",
        "300750.SZ",
        "801010.SI",
        "000300.SH",
        "399006.SZ",
    ]
    assert filter_industry_codes(codes) == ["801010.SI", "000300.SH", "399006.SZ"]
    kept = filter_industry_codes(
        ["600000.SH", "801020.SI"],
        details={"600000.SH": {"InstrumentName": "SW银行"}, "801020.SI": {"InstrumentName": "SW采掘"}},
    )
    assert kept == ["801020.SI"]


def test_pick_industry_sector_prefers_xuntou_name():
    assert pick_industry_sector(["沪深A股", "迅投一级行业板块指数", "概念指数"]) == "迅投一级行业板块指数"
    assert pick_industry_sector(["申万一级行业指数", "二级行业指数"]) == "申万一级行业指数"
    assert pick_industry_sector(["沪深A股", "银行"]) is None


def test_index_sync_window_rules():
    job_start, job_end = "2026-08-13", "2026-08-18"
    b_start, b_end = index_sync_window(
        kind="benchmark", has_rows=False, job_start=job_start, job_end=job_end
    )
    assert b_end == job_end
    assert b_start < "2008-01-01"

    i_start, i_end = index_sync_window(
        kind="industry", has_rows=False, job_start=job_start, job_end=job_end
    )
    assert (i_start, i_end) == (job_start, job_end)

    full_start, full_end = resolve_range_preset("10y", max_date=job_end)
    cap_start, cap_end = resolve_range_preset("3y", max_date=job_end)
    ind_full_start, ind_full_end = index_sync_window(
        kind="industry", has_rows=False, job_start=full_start, job_end=full_end
    )
    assert ind_full_start == cap_start
    assert ind_full_end == cap_end

    assert index_sync_window(
        kind="benchmark", has_rows=True, job_start=job_start, job_end=job_end
    ) == (job_start, job_end)

    assert index_sync_window(
        kind="benchmark",
        has_rows=False,
        job_start=full_start,
        job_end=full_end,
        repair=True,
        lookback_start="2026-01-01",
        lookback_end="2026-08-01",
    ) == ("2026-01-01", "2026-08-01")


def _bar_frame():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
            "volume": [10, 11],
            "amount": [11, 13],
            "pre_close": [1.0, 1.1],
        },
        index=idx,
    )


def test_index_sync_writes_index_table_not_daily_bar(db):
    from qmt_quant.core.sync.index_sync import sync_index_bars

    client = MagicMock()
    client.get_sector_list.return_value = []
    client.fetch_market_bars.return_value = {"000300.SH": _bar_frame()}

    result = sync_index_bars(
        client=client,
        job_start="2024-01-01",
        job_end="2024-01-03",
        repair=False,
    )
    assert result["index_codes"] == 8
    assert result["industry_source_sector"] is None
    assert "000300.SH" not in (result.get("index_failed") or [])

    with db_session(db) as conn:
        stock = conn.execute(
            "SELECT COUNT(*) FROM daily_bar WHERE code = %s", ("000300.SH",)
        ).fetchone()[0]
        idx_n = conn.execute(
            "SELECT COUNT(*) FROM index_daily_bar WHERE code = %s", ("000300.SH",)
        ).fetchone()[0]
        inst = conn.execute(
            "SELECT kind FROM index_instrument WHERE code = %s", ("000300.SH",)
        ).fetchone()
        stock_inst = conn.execute(
            "SELECT COUNT(*) FROM instrument WHERE code = %s", ("000300.SH",)
        ).fetchone()[0]
    assert stock == 0
    assert idx_n == 2
    assert inst[0] == "benchmark"
    assert stock_inst == 0


def test_industry_discovery_failure_still_syncs_benchmark(db):
    from qmt_quant.core.sync.index_sync import sync_index_bars

    client = MagicMock()
    client.get_sector_list.side_effect = RuntimeError("no sector api")
    client.fetch_market_bars.return_value = {"000001.SH": _bar_frame()}

    result = sync_index_bars(
        client=client, job_start="2024-01-01", job_end="2024-01-03"
    )
    assert result["index_codes"] == 8
    assert result["industry_source_sector"] is None
    with db_session(db) as conn:
        kinds = {
            r[0]
            for r in conn.execute("SELECT DISTINCT kind FROM index_instrument").fetchall()
        }
    assert kinds == {"benchmark"}


def test_industry_constituents_not_fetched(db):
    from qmt_quant.core.sync.index_sync import sync_index_bars

    client = MagicMock()
    client.get_sector_list.return_value = ["迅投一级行业板块指数"]
    client.get_sector_stocks.return_value = ["600000.SH", "000001.SZ", "801010.SI"]
    client.get_instrument_detail.side_effect = lambda code: {
        "600000.SH": {"InstrumentName": "浦发银行"},
        "000001.SZ": {"InstrumentName": "平安银行"},
        "801010.SI": {"InstrumentName": "SW农林牧渔"},
    }.get(code, {})
    client.fetch_market_bars.return_value = {
        "000300.SH": _bar_frame(),
        "801010.SI": _bar_frame(),
    }

    result = sync_index_bars(
        client=client, job_start="2024-01-01", job_end="2024-01-03"
    )
    all_codes = []
    for call in client.fetch_market_bars.call_args_list:
        all_codes.extend(list(call.args[0]))
    assert "600000.SH" not in all_codes
    assert "000001.SZ" not in all_codes
    assert "801010.SI" in all_codes
    assert result["industry_source_sector"] == "迅投一级行业板块指数"
    with db_session(db) as conn:
        row = conn.execute(
            "SELECT kind, source_sector FROM index_instrument WHERE code = %s",
            ("801010.SI",),
        ).fetchone()
        daily = conn.execute(
            "SELECT COUNT(*) FROM daily_bar WHERE code = ANY(%s)",
            (["600000.SH", "801010.SI"],),
        ).fetchone()[0]
    assert row == ("industry", "迅投一级行业板块指数")
    assert daily == 0


def test_index_failure_does_not_fail_stock_sync():
    from qmt_quant.core.sync import bars as bars_mod

    settings = MagicMock()
    settings.sync_incremental_days = 5
    settings.sync_batch_size = 50
    settings.sync_auto_repair = False
    settings.sync_name_backfill_on_incremental = False
    settings.auto_export_catalog = False

    with patch.object(bars_mod, "run_migrations"):
        with patch.object(bars_mod, "resolve_universe", return_value=["600519.SH"]):
            with patch.object(bars_mod, "db_session") as mock_db:
                mock_db.return_value.__enter__.return_value = MagicMock()
                with patch.object(bars_mod, "record_universe_count"):
                    with patch.object(bars_mod, "ensure_instrument_codes"):
                        with patch.object(bars_mod, "_fetch_and_upsert", return_value=7):
                            with patch.object(bars_mod, "market_latest_date", return_value=None):
                                with patch.object(bars_mod, "sync_calendar_from_qmt"):
                                    with patch.object(bars_mod, "XtDataClient"):
                                        with patch.object(bars_mod, "get_settings", return_value=settings):
                                            with patch(
                                                "qmt_quant.storage.instruments.count_missing_names",
                                                return_value=0,
                                            ):
                                                with patch(
                                                    "qmt_quant.core.sync.index_sync.sync_index_bars",
                                                    side_effect=RuntimeError("qmt timeout"),
                                                ):
                                                    result = bars_mod.sync_bars(
                                                        incremental=True, mode="incremental"
                                                    )
    assert result["bars_written"] == 7
    assert result["index_failed"] == ["*"]


def test_stock_error_still_attempts_index_sync():
    from qmt_quant.core.sync import bars as bars_mod

    settings = MagicMock()
    settings.sync_incremental_days = 5
    settings.sync_batch_size = 50
    settings.sync_auto_repair = False
    settings.sync_name_backfill_on_incremental = True
    settings.auto_export_catalog = False

    with patch.object(bars_mod, "run_migrations"):
        with patch.object(bars_mod, "resolve_universe", return_value=["600519.SH"]):
            with patch.object(bars_mod, "db_session") as mock_db:
                mock_db.return_value.__enter__.return_value = MagicMock()
                with patch.object(bars_mod, "record_universe_count"):
                    with patch.object(bars_mod, "ensure_instrument_codes"):
                        with patch.object(
                            bars_mod, "_fetch_and_upsert", side_effect=RuntimeError("stock fail")
                        ):
                            with patch.object(bars_mod, "market_latest_date", return_value=None):
                                with patch.object(bars_mod, "sync_calendar_from_qmt"):
                                    with patch.object(bars_mod, "XtDataClient"):
                                        with patch.object(bars_mod, "get_settings", return_value=settings):
                                            with patch(
                                                "qmt_quant.core.sync.index_sync.sync_index_bars",
                                                return_value={
                                                    "index_codes": 8,
                                                    "index_bars_written": 1,
                                                    "index_failed": [],
                                                    "industry_source_sector": None,
                                                },
                                            ) as idx:
                                                with pytest.raises(RuntimeError, match="stock fail"):
                                                    bars_mod.sync_bars(
                                                        incremental=True, mode="incremental"
                                                    )
                                                idx.assert_called_once()


def test_resolve_universe_does_not_inject_benchmarks(monkeypatch):
    monkeypatch.setattr(
        "qmt_quant.core.sync.universe.XtDataClient",
        lambda: type(
            "C",
            (),
            {"get_sector_stocks": staticmethod(lambda sector: ["600519.SH", "000001.SZ"])},
        )(),
    )
    codes = resolve_universe("沪深A股")
    assert "000300.SH" not in codes
    assert codes == ["600519.SH", "000001.SZ"]


def test_query_index_daily_bar_includes_kind_and_name(db):
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
        result = query_table(
            conn,
            "index_daily_bar",
            "cross_section",
            date="2024-01-02",
        )
    assert result["total"] == 1
    row = result["rows"][0]
    assert row["code"] == "000300.SH"
    assert row["name"] == "沪深300"
    assert row["kind"] == "基准"


def test_kline_index_ignores_front_adjust(db):
    with db_session(db) as conn:
        upsert_index_instruments(conn, [("000300.SH", "沪深300", "benchmark", None)])
        upsert_index_bars(
            conn,
            [
                IndexBarRow(
                    code="000300.SH",
                    date="2024-01-02",
                    open=10,
                    high=11,
                    low=9,
                    close=10.5,
                    volume=100,
                    amount=1050,
                )
            ],
        )
        payload = build_kline_payload(conn, "000300.SH", adjust="front")
    assert payload["empty"] is False
    assert payload["adjust"] == "none"
    assert payload["ohlc"][0] == [10, 10.5, 9, 11]
