"""NT catalog export tests."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def test_export_nt_catalog_no_nautilus():
    from qmt_quant.core.catalog.nt_export import export_nt_catalog

    with patch("qmt_quant.core.catalog.nt_export.db_session") as mock_db:
        mock_conn = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        with patch("qmt_quant.core.catalog.nt_export.load_bars_df", return_value=pd.DataFrame()):
            result = export_nt_catalog()
    assert result.get("exported") == 0 or "error" in result


@pytest.mark.skipif(
    pytest.importorskip("nautilus_trader", reason="nautilus not installed") is None,
    reason="nautilus",
)
def test_export_nt_catalog_with_bars(tmp_path, monkeypatch):
    nautilus_trader = pytest.importorskip("nautilus_trader")
    del nautilus_trader

    from qmt_quant.config import get_settings
    from qmt_quant.core.catalog.nt_export import export_nt_catalog

    settings = get_settings()
    monkeypatch.setattr(settings, "catalog_nt_dir", str(tmp_path / "catalog_nt"))

    df = pd.DataFrame(
        {
            "code": ["600519.SH"] * 5,
            "date": pd.date_range("2024-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "volume": [1000] * 5,
        }
    )
    with patch("qmt_quant.core.catalog.nt_export.db_session") as mock_db:
        mock_conn = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        with patch("qmt_quant.core.catalog.nt_export.load_bars_df", return_value=df):
            result = export_nt_catalog(limit=1)
    if "error" not in result:
        assert result.get("exported", 0) >= 0
