"""sync_bars parameter compatibility."""

from unittest.mock import MagicMock, patch

from qmt_quant.core.sync.bars import sync_bars


def test_sync_bars_accepts_range_preset_all():
    client = MagicMock()
    with patch("qmt_quant.core.sync.bars.XtDataClient", return_value=client):
        with patch("qmt_quant.core.sync.bars.resolve_universe", return_value=[]):
            with patch("qmt_quant.core.sync.bars._fetch_and_upsert", return_value=0):
                with patch("qmt_quant.core.sync.bars.sync_calendar_from_qmt"):
                    with patch(
                        "qmt_quant.core.sync.index_sync.sync_index_bars",
                        return_value={
                            "index_codes": 0,
                            "index_bars_written": 0,
                            "index_failed": [],
                            "industry_source_sector": None,
                        },
                    ):
                        result = sync_bars(
                            sector="沪深A股",
                            incremental=False,
                            range_preset="all",
                            adjust_type="front",
                        )
    assert result["start"] == "2005-01-01"
    assert result["range_preset"] == "all"
    assert result["mode"] == "full"


def test_sync_bars_full_via_start_date_despite_default_mode():
    """Web jobs pass incremental=False + start_date but omit mode; must not fall back to incremental."""
    client = MagicMock()
    with patch("qmt_quant.core.sync.bars.XtDataClient", return_value=client):
        with patch("qmt_quant.core.sync.bars.resolve_universe", return_value=[]):
            with patch("qmt_quant.core.sync.bars._fetch_and_upsert", return_value=0):
                with patch("qmt_quant.core.sync.bars.sync_calendar_from_qmt"):
                    with patch(
                        "qmt_quant.core.sync.index_sync.sync_index_bars",
                        return_value={
                            "index_codes": 0,
                            "index_bars_written": 0,
                            "index_failed": [],
                            "industry_source_sector": None,
                        },
                    ):
                        result = sync_bars(
                            sector="沪深A股",
                            incremental=False,
                            start_date="2005-01-01",
                            range_preset="all",
                            adjust_type="front",
                        )
    assert result["mode"] == "full"
    assert result["start"] == "2005-01-01"
    assert result["range_preset"] == "all"
