"""Watchlist file helpers."""

from pathlib import Path

import pytest

from qmt_quant.core.watchlist import WATCHLIST_HEADER, normalize_watchlist_codes, read_watchlist_codes, save_watchlist


def test_normalize_watchlist_codes_dedupes():
    codes = normalize_watchlist_codes(["600519", "600519.SH", " 000001.SZ ", ""])
    assert codes == ["600519.SH", "000001.SZ"]


def test_normalize_watchlist_rejects_name_only():
    import pytest

    with pytest.raises(ValueError, match="无法识别"):
        normalize_watchlist_codes(["招商银行"])


def test_save_watchlist_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "watchlist.txt"

    class FakeSettings:
        watchlist_path = str(path)

        def resolve_path(self, p: str) -> Path:
            return Path(p)

    monkeypatch.setattr("qmt_quant.core.watchlist.get_settings", lambda: FakeSettings())

    saved = save_watchlist(["600519.SH", "000001.SZ"])
    assert saved == ["600519.SH", "000001.SZ"]
    text = path.read_text(encoding="utf-8")
    assert text.startswith(WATCHLIST_HEADER)
    assert read_watchlist_codes(path) == saved
