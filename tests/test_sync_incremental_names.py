"""Incremental sync should not block on bulk name backfill."""

import pytest

pytest.importorskip("psycopg")

from unittest.mock import MagicMock, patch


def test_incremental_skips_name_backfill_by_default():
    from qmt_quant.core.sync import bars as bars_mod

    settings = MagicMock()
    settings.sync_incremental_days = 5
    settings.sync_batch_size = 50
    settings.sync_auto_repair = False
    settings.sync_name_backfill_on_incremental = False
    settings.auto_export_catalog = False

    client = MagicMock()
    with patch.object(bars_mod, "run_migrations"):
        with patch.object(bars_mod, "resolve_universe", return_value=["600519.SH"]):
            with patch.object(bars_mod, "db_session") as mock_db:
                conn = MagicMock()
                mock_db.return_value.__enter__.return_value = conn
                with patch.object(bars_mod, "record_universe_count"):
                    with patch.object(bars_mod, "ensure_instrument_codes"):
                        with patch.object(bars_mod, "_fetch_and_upsert", return_value=1):
                            with patch.object(bars_mod, "market_latest_date", return_value=None):
                                with patch.object(bars_mod, "sync_calendar_from_qmt"):
                                    with patch.object(bars_mod, "XtDataClient", return_value=client):
                                        with patch(
                                            "qmt_quant.storage.instruments.count_missing_names",
                                            return_value=5108,
                                        ) as mock_count:
                                            with patch(
                                                "qmt_quant.storage.instruments.backfill_names_after_sync"
                                            ) as mock_backfill:
                                                with patch.object(
                                                    bars_mod, "get_settings", return_value=settings
                                                ):
                                                    with patch(
                                                        "qmt_quant.core.sync.index_sync.sync_index_bars",
                                                        return_value={
                                                            "index_codes": 0,
                                                            "index_bars_written": 0,
                                                            "index_failed": [],
                                                            "industry_source_sector": None,
                                                        },
                                                    ):
                                                        result = bars_mod.sync_bars(
                                                            incremental=True,
                                                            mode="incremental",
                                                        )
    mock_backfill.assert_not_called()
    mock_count.assert_called_once()
    assert result["names_skipped"] == 5108
