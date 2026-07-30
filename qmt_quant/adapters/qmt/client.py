"""QMT xtdata client wrapper."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from qmt_quant.core.doctor import ensure_xtquant_path


@dataclass
class DownloadStats:
    success: int = 0
    failed: int = 0
    failed_codes: List[str] | None = None

    def __post_init__(self) -> None:
        if self.failed_codes is None:
            self.failed_codes = []


class XtDataClient:
    """Thin wrapper around xtquant.xtdata with graceful import errors."""

    def __init__(self) -> None:
        ensure_xtquant_path()
        try:
            from xtquant import xtdata  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "xtquant not available. Start QMT and configure xtquant path in settings."
            ) from exc
        self._xt = xtdata

    def get_sector_stocks(self, sector: str) -> List[str]:
        codes = self._xt.get_stock_list_in_sector(sector)
        return [normalize_code(c) for c in codes]

    def get_instrument_detail(self, code: str) -> Dict[str, Any]:
        detail = self._xt.get_instrument_detail(code)
        return detail or {}

    def download_history(
        self,
        codes: Sequence[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
    ) -> DownloadStats:
        stats = DownloadStats()
        for code in codes:
            try:
                if hasattr(self._xt, "download_history_data2"):
                    self._xt.download_history_data2(
                        stock_list=[code],
                        period=period,
                        start_time=start_time,
                        end_time=end_time,
                    )
                else:
                    self._xt.download_history_data(
                        code, period=period, start_time=start_time, end_time=end_time
                    )
                stats.success += 1
            except Exception:
                stats.failed += 1
                stats.failed_codes.append(code)
            time.sleep(0.01)
        return stats

    def get_market_bars(
        self,
        codes: Sequence[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "front",
    ) -> Dict[str, pd.DataFrame]:
        fields = ["open", "high", "low", "close", "volume", "amount", "preClose"]
        if hasattr(self._xt, "get_market_data_ex"):
            raw = self._xt.get_market_data_ex(
                field_list=fields,
                stock_list=list(codes),
                period=period,
                start_time=start_time,
                end_time=end_time,
                dividend_type=dividend_type,
                fill_data=True,
            )
        else:
            raw = self._xt.get_market_data(
                field_list=fields,
                stock_list=list(codes),
                period=period,
                start_time=start_time,
                end_time=end_time,
                dividend_type=dividend_type,
            )
        return self._normalize_market_data(raw, codes)

    def download_financial(self, codes: Sequence[str], table_list: Sequence[str]) -> DownloadStats:
        stats = DownloadStats()
        try:
            if hasattr(self._xt, "download_financial_data2"):
                self._xt.download_financial_data2(list(codes), list(table_list))
                stats.success = len(codes)
            else:
                for code in codes:
                    self._xt.download_financial_data(code, list(table_list))
                    stats.success += 1
        except Exception:
            stats.failed = len(codes)
            stats.failed_codes = list(codes)
        return stats

    def get_financial_data(
        self,
        codes: Sequence[str],
        table_list: Sequence[str],
        start_time: str = "",
        end_time: str = "",
        report_type: str = "report_time",
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        return self._xt.get_financial_data(
            stock_list=list(codes),
            table_list=list(table_list),
            start_time=start_time,
            end_time=end_time,
            report_type=report_type,
        )

    @staticmethod
    def _normalize_market_data(raw: Any, codes: Sequence[str]) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        if raw is None:
            return out
        if isinstance(raw, dict) and codes and isinstance(raw.get(codes[0]), pd.DataFrame):
            return {normalize_code(k): v for k, v in raw.items()}
        if isinstance(raw, dict) and "close" in raw:
            close_df = raw["close"]
            if isinstance(close_df, pd.DataFrame):
                for code in close_df.columns:
                    frame = pd.DataFrame(index=close_df.index)
                    for field, df in raw.items():
                        if isinstance(df, pd.DataFrame) and code in df.columns:
                            frame[field.lower().replace("preclose", "pre_close")] = df[code]
                    out[normalize_code(code)] = frame
        return out


def normalize_code(code: str) -> str:
    code = code.strip().upper()
    if "." in code:
        return code
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def to_qmt_date(date_str: str) -> str:
    return date_str.replace("-", "")
