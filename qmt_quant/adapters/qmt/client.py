"""QMT xtdata client wrapper."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from qmt_quant.adapters.qmt.runtime import XtDataBridgeClient, resolve_xtquant_port, should_use_x64_bridge
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
    """Thin wrapper around xtquant.xtdata; uses QMT x64 bridge on ARM64 hosts."""

    def __init__(self) -> None:
        self._bridge: Optional[XtDataBridgeClient] = None
        self._xt = None
        if should_use_x64_bridge():
            self._bridge = XtDataBridgeClient()
            return
        ensure_xtquant_path()
        try:
            from xtquant import xtdata  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "xtquant not available. Start QMT and configure xtquant path in settings."
            ) from exc
        if hasattr(xtdata, "connect"):
            try:
                xtdata.connect("", resolve_xtquant_port())
            except Exception:
                pass
        self._xt = xtdata

    def get_sector_stocks(self, sector: str) -> List[str]:
        if self._bridge:
            return [normalize_code(c) for c in self._bridge.get_sector_stocks(sector)]
        codes = self._xt.get_stock_list_in_sector(sector)
        return [normalize_code(c) for c in codes]

    def get_sector_list(self) -> List[str]:
        if self._bridge:
            return list(self._bridge.get_sector_list())
        names = []
        if self._xt is not None and hasattr(self._xt, "get_sector_list"):
            try:
                names = self._xt.get_sector_list() or []
            except Exception:
                names = []
        return [str(s).strip() for s in names if str(s).strip()]

    def get_instrument_detail(self, code: str) -> Dict[str, Any]:
        if self._bridge:
            return self._bridge.get_instrument_detail(code)
        detail = self._xt.get_instrument_detail(code)
        return detail or {}

    def download_history(
        self,
        codes: Sequence[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
    ) -> DownloadStats:
        if self._bridge:
            raw = self._bridge.download_history(list(codes), period, start_time, end_time)
            return DownloadStats(
                success=int(raw.get("success", 0)),
                failed=int(raw.get("failed", 0)),
                failed_codes=list(raw.get("failed_codes") or []),
            )
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
        if self._bridge:
            raw = self._bridge.get_market_bars(
                list(codes), period, start_time, end_time, dividend_type
            )
            return {normalize_code(k): v for k, v in raw.items()}
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

    def fetch_market_bars(
        self,
        codes: Sequence[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "front",
    ) -> Dict[str, pd.DataFrame]:
        if self._bridge:
            raw = self._bridge.fetch_market_bars(
                list(codes), period, start_time, end_time, dividend_type
            )
            return {normalize_code(k): v for k, v in raw.items()}
        self.download_history(codes, period=period, start_time=start_time, end_time=end_time)
        return self.get_market_bars(
            codes,
            period=period,
            start_time=start_time,
            end_time=end_time,
            dividend_type=dividend_type,
        )

    def download_financial(self, codes: Sequence[str], table_list: Sequence[str]) -> DownloadStats:
        if self._bridge:
            raw = self._bridge.download_financial(list(codes), list(table_list))
            return DownloadStats(
                success=int(raw.get("success", 0)),
                failed=int(raw.get("failed", 0)),
                failed_codes=list(raw.get("failed_codes") or []),
            )
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
        if self._bridge:
            return self._bridge.get_financial_data(
                list(codes), list(table_list), start_time, end_time, report_type
            )
        return self._xt.get_financial_data(
            stock_list=list(codes),
            table_list=list(table_list),
            start_time=start_time,
            end_time=end_time,
            report_type=report_type,
        )

    def fetch_financial_data(
        self,
        codes: Sequence[str],
        table_list: Sequence[str],
        start_time: str = "",
        end_time: str = "",
        report_type: str = "report_time",
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        if self._bridge:
            return self._bridge.fetch_financial_data(
                list(codes), list(table_list), start_time, end_time, report_type
            )
        self.download_financial(codes, table_list)
        return self.get_financial_data(
            codes,
            table_list,
            start_time=start_time,
            end_time=end_time,
            report_type=report_type,
        )

    def get_trading_dates(
        self,
        *,
        market: str = "SH",
        start_date: str = "",
        end_date: str = "",
    ) -> List[str]:
        """Return ISO trading dates; fallback to index 000001.SH bars."""
        start_qmt = to_qmt_date(start_date) if start_date else ""
        end_qmt = to_qmt_date(end_date) if end_date else ""
        if self._bridge:
            raw = self._bridge.get_trading_dates(market, start_qmt, end_qmt)
            return list(raw)
        if self._xt is not None and hasattr(self._xt, "get_trading_dates"):
            try:
                raw = self._xt.get_trading_dates(market, start_qmt, end_qmt)
                return [_from_qmt_date(str(d)) for d in (raw or [])]
            except Exception:
                pass
        ref_code = "000001.SH" if market.upper() in ("SH", "SSE", "") else "399001.SZ"
        bars = self.get_market_bars(
            [ref_code],
            period="1d",
            start_time=start_qmt,
            end_time=end_qmt,
            dividend_type="none",
        )
        frame = bars.get(ref_code)
        if frame is None or frame.empty:
            return []
        if not isinstance(frame.index, pd.DatetimeIndex):
            frame.index = pd.to_datetime(frame.index)
        return sorted(pd.Timestamp(ts).strftime("%Y-%m-%d") for ts in frame.index)

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
    raw = code.strip().upper()
    match = re.match(r"^(\d{6})(?:\.(SH|SZ))?$", raw)
    if match:
        digits, suffix = match.group(1), match.group(2)
        if suffix:
            return f"{digits}.{suffix}"
        if digits.startswith(("6", "5", "9")):
            return f"{digits}.SH"
        return f"{digits}.SZ"
    if "." in raw:
        base, suffix = raw.rsplit(".", 1)
        if suffix in ("SH", "SZ") and re.fullmatch(r"\d{6}", base):
            return f"{base}.{suffix}"
    return raw


def to_qmt_date(date_str: str) -> str:
    return date_str.replace("-", "")


def _from_qmt_date(raw: str) -> str:
    s = raw.replace("-", "")[:8]
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return raw
