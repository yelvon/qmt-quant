"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]


def _find_settings_path() -> Path:
    for name in ("config/settings.yaml", "config/settings.yaml.example"):
        p = ROOT_DIR / name
        if p.exists():
            return p
    return ROOT_DIR / "config" / "settings.yaml.example"


@dataclass
class Settings:
    qmt_install_dir: str = r"C:\qmt"
    xtquant_site_packages: str = ""
    userdata_path: str = ""
    account_id: str = ""
    qmt_python: str = ""
    quant_python: str = ""
    db_path: str = "data/qmt_quant.db"
    parquet_catalog_dir: str = "data/catalog"
    watchlist_path: str = "config/watchlist.txt"
    default_sector: str = "沪深A股"
    bar_adjust_type: str = "front"
    sync_batch_size: int = 50
    auto_export_catalog: bool = True
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_commission: float = 5.0
    transfer_fee_rate: float = 0.00002
    slippage_bps: float = 5.0
    match_price: str = "next_open"
    max_weight_per_symbol: float = 0.1
    dry_run: bool = True
    web_host: str = "127.0.0.1"
    web_port: int = 8788
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        path = path or _find_settings_path()
        raw: Dict[str, Any] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        qmt = raw.get("qmt", {})
        py = raw.get("python", {})
        data = raw.get("data", {})
        bt = raw.get("backtest", {})
        trade = raw.get("trade", {})
        web = raw.get("web", {})
        return cls(
            qmt_install_dir=qmt.get("install_dir", cls.qmt_install_dir),
            xtquant_site_packages=qmt.get("xtquant_site_packages", ""),
            userdata_path=qmt.get("userdata_path", ""),
            account_id=qmt.get("account_id", ""),
            qmt_python=py.get("qmt_env", os.environ.get("QMT_PYTHON", "")),
            quant_python=py.get("quant_env", os.environ.get("QUANT_PYTHON", "")),
            db_path=os.environ.get("QMT_QUANT_DB") or data.get("db_path", cls.db_path),
            parquet_catalog_dir=data.get("parquet_catalog_dir", cls.parquet_catalog_dir),
            watchlist_path=data.get("watchlist_path", cls.watchlist_path),
            default_sector=data.get("default_sector", cls.default_sector),
            bar_adjust_type=data.get("bar_adjust_type", cls.bar_adjust_type),
            sync_batch_size=int(data.get("sync_batch_size", cls.sync_batch_size)),
            auto_export_catalog=bool(data.get("auto_export_catalog", cls.auto_export_catalog)),
            initial_cash=float(bt.get("initial_cash", cls.initial_cash)),
            commission_rate=float(bt.get("commission_rate", cls.commission_rate)),
            stamp_tax_rate=float(bt.get("stamp_tax_rate", cls.stamp_tax_rate)),
            min_commission=float(bt.get("min_commission", cls.min_commission)),
            transfer_fee_rate=float(bt.get("transfer_fee_rate", cls.transfer_fee_rate)),
            slippage_bps=float(bt.get("slippage_bps", cls.slippage_bps)),
            match_price=bt.get("match_price", cls.match_price),
            max_weight_per_symbol=float(bt.get("max_weight_per_symbol", cls.max_weight_per_symbol)),
            dry_run=bool(trade.get("dry_run", cls.dry_run)),
            web_host=web.get("host", cls.web_host),
            web_port=int(web.get("port", cls.web_port)),
            _raw=raw,
        )

    def resolve_path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def db_file(self) -> Path:
        return self.resolve_path(self.db_path)

    @property
    def catalog_dir(self) -> Path:
        return self.resolve_path(self.parquet_catalog_dir)


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings
