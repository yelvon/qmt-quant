"""Streaming catalog export — must not load full market into memory."""

from unittest.mock import MagicMock, patch

import pandas as pd

from qmt_quant.core.catalog.export import export_catalog


def test_export_catalog_streams_per_code(tmp_path, monkeypatch):
    monkeypatch.setenv("QMT_QUANT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "qmt_quant.core.catalog.export.get_settings",
        lambda: MagicMock(
            catalog_dir=tmp_path / "catalog",
            export_nt_catalog=False,
        ),
    )

    codes = ["000001.SZ", "600519.SH"]
    frames = {
        "000001.SZ": pd.DataFrame({"code": ["000001.SZ"], "date": ["2026-01-02"], "close": [10.0]}),
        "600519.SH": pd.DataFrame({"code": ["600519.SH"], "date": ["2026-01-02"], "close": [1800.0]}),
    }
    load_calls: list[list[str] | None] = []

    def fake_load(conn, *, codes=None, adjust_type="front", **kwargs):
        load_calls.append(list(codes) if codes else None)
        return frames[codes[0]].copy()

    with patch("qmt_quant.core.catalog.export.run_migrations"):
        with patch("qmt_quant.core.catalog.export.db_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            with patch("qmt_quant.core.catalog.export.list_bar_codes", return_value=codes):
                with patch("qmt_quant.core.catalog.export.load_bars_df", side_effect=fake_load):
                    result = export_catalog(adjust_type="front")

    assert result["exported"] == 2
    assert load_calls == [["000001.SZ"], ["600519.SH"]]
    assert (tmp_path / "catalog" / "catalog_meta.json").exists()


def test_export_catalog_honors_codes_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("QMT_QUANT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "qmt_quant.core.catalog.export.get_settings",
        lambda: MagicMock(
            catalog_dir=tmp_path / "catalog",
            export_nt_catalog=False,
        ),
    )

    frame = pd.DataFrame({"code": ["600519.SH"], "date": ["2026-01-02"], "close": [1800.0]})
    load_calls: list[list[str] | None] = []

    def fake_load(conn, *, codes=None, adjust_type="front", **kwargs):
        load_calls.append(list(codes) if codes else None)
        return frame.copy()

    with patch("qmt_quant.core.catalog.export.run_migrations"):
        with patch("qmt_quant.core.catalog.export.db_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            with patch("qmt_quant.core.catalog.export.load_bars_df", side_effect=fake_load):
                result = export_catalog(adjust_type="front", codes=["600519.SH"])

    assert result["exported"] == 1
    assert load_calls == [["600519.SH"]]
