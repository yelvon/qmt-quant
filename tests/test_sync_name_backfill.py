"""Sync-time instrument name backfill tests."""

from unittest.mock import patch

import pytest


def test_backfill_after_sync_batches_missing_only():
    pytest.importorskip("psycopg")
    from qmt_quant.core.sync.universe import backfill_instrument_names_after_sync

    conn = object()
    with patch(
        "qmt_quant.storage.instruments.fetch_and_store_names",
        return_value=2,
    ) as mock_fetch:
        updated = backfill_instrument_names_after_sync(
            conn,
            ["600519.SH", "000001.SZ", "600036.SH"],
            client=object(),
            batch_size=50,
        )
    assert updated == 2
    mock_fetch.assert_called_once()
