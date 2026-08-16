"""Instrument name cache tests."""

import pytest

pytest.importorskip("psycopg")

from unittest.mock import MagicMock, patch

from qmt_quant.storage.instruments import (
    NAME_MISSING_SQL,
    backfill_names_after_sync,
    fetch_and_store_names,
    name_is_missing,
)


def test_name_is_missing():
    assert name_is_missing("600519.SH", None)
    assert name_is_missing("600519.SH", "")
    assert name_is_missing("600519.SH", "600519.SH")
    assert name_is_missing("600519.SH", "600519")
    assert not name_is_missing("600519.SH", "贵州茅台")


def test_name_missing_sql_covers_empty_trim():
    assert "btrim" in NAME_MISSING_SQL


def test_backfill_after_sync_delegates_to_fetch():
    conn = MagicMock()
    with patch(
        "qmt_quant.storage.instruments.fetch_and_store_names",
        return_value=2,
    ) as mock_fetch:
        updated = backfill_names_after_sync(
            conn,
            ["600519.SH", "000001.SZ"],
            client=object(),
            batch_size=50,
        )
    assert updated == 2
    mock_fetch.assert_called_once_with(
        conn,
        ["600519.SH", "000001.SZ"],
        client=mock_fetch.call_args.kwargs["client"],
        job_id=None,
        batch_size=50,
    )


def test_fetch_and_store_skips_when_no_missing():
    conn = MagicMock()
    with patch("qmt_quant.storage.instruments.ensure_codes"):
        with patch(
            "qmt_quant.storage.instruments.list_missing_name_codes",
            return_value=[],
        ):
            assert fetch_and_store_names(conn, ["600519.SH"]) == 0


def test_fetch_and_store_only_queries_missing():
    conn = MagicMock()
    client = MagicMock()
    client.get_instrument_detail.return_value = {"InstrumentName": "贵州茅台"}

    with patch("qmt_quant.storage.instruments.ensure_codes"):
        with patch(
            "qmt_quant.storage.instruments.list_missing_name_codes",
            return_value=["600519.SH"],
        ):
            with patch("qmt_quant.storage.instruments.qmt_semaphore"):
                with patch("qmt_quant.storage.instruments.upsert_profile") as mock_upsert:
                    updated = fetch_and_store_names(conn, ["600519.SH"], client=client)
    assert updated == 1
    client.get_instrument_detail.assert_called_once_with("600519.SH")
    mock_upsert.assert_called_once()
