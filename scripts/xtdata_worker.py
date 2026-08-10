# -*- coding: utf-8 -*-
"""Minimal xtdata worker for QMT x64 pythonw (3.6+). stdin JSON -> file JSON."""

from __future__ import print_function

import json
import os
import sys
import traceback


def _df_to_split(df):
    if df is None:
        return None
    if hasattr(df, "to_json"):
        return df.to_json(orient="split", date_format="iso")
    return None


def _bootstrap_import_path():
    xt_path = os.environ.get("XTQUANT_SITE_PACKAGES", "").strip()
    cleaned = []
    for entry in sys.path:
        norm = entry.replace("\\", "/").lower()
        if "python312-arm64" in norm or "python313-arm64" in norm:
            continue
        cleaned.append(entry)
    sys.path = cleaned
    if xt_path:
        sys.path.insert(0, xt_path)


def _ensure_connect(xtdata, port_override=None):
    preferred_ports = []
    if port_override is not None:
        preferred_ports.append(int(port_override))
    for key in ("QMT_XTQUANT_PORT", "XTQUANT_PORT"):
        val = os.environ.get(key, "").strip()
        if val.isdigit():
            preferred_ports.append(int(val))
    preferred_ports.extend([58610, 58609, 58601, 58600])

    if hasattr(xtdata, "connect"):
        for port in preferred_ports:
            try:
                xtdata.connect(ip="", port=port)
                return
            except Exception:
                continue
        try:
            xtdata.connect()
            return
        except Exception:
            pass
    try:
        from xtquant import xtconn

        servers = xtconn.scan_available_server_addr()
        for addr in servers:
            try:
                port = int(str(addr).split(":")[-1])
                xtdata.connect(ip="", port=port)
                return
            except Exception:
                continue
    except Exception:
        pass


def _cmd_get_sector_stocks(xtdata, params):
    _ensure_connect(xtdata)
    sector = params.get("sector", "沪深A股")
    codes = xtdata.get_stock_list_in_sector(sector)
    return {"codes": list(codes or [])}


def _cmd_get_instrument_detail(xtdata, params):
    _ensure_connect(xtdata)
    code = params["code"]
    try:
        detail = xtdata.get_instrument_detail(code) or {}
    except Exception:
        detail = {}
    return {"detail": detail}


def _cmd_download_history(xtdata, params):
    _ensure_connect(xtdata)
    codes = list(params.get("codes") or [])
    period = params.get("period", "1d")
    start_time = params.get("start_time", "")
    end_time = params.get("end_time", "")
    if not codes:
        return {"success": 0, "failed": 0, "failed_codes": []}
    if hasattr(xtdata, "download_history_data2"):
        try:
            xtdata.download_history_data2(
                stock_list=codes,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )
            return {"success": len(codes), "failed": 0, "failed_codes": []}
        except Exception:
            pass
    ok, failed = 0, []
    for code in codes:
        try:
            if hasattr(xtdata, "download_history_data2"):
                xtdata.download_history_data2(
                    stock_list=[code],
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                )
            else:
                xtdata.download_history_data(
                    code, period=period, start_time=start_time, end_time=end_time
                )
            ok += 1
        except Exception:
            failed.append(code)
    return {"success": ok, "failed": len(failed), "failed_codes": failed}


def _cmd_get_market_bars(xtdata, params):
    _ensure_connect(xtdata)
    codes = params.get("codes") or []
    fields = ["open", "high", "low", "close", "volume", "amount", "preClose"]
    period = params.get("period", "1d")
    start_time = params.get("start_time", "")
    end_time = params.get("end_time", "")
    dividend_type = params.get("dividend_type", "front")
    if hasattr(xtdata, "get_market_data_ex"):
        raw = xtdata.get_market_data_ex(
            field_list=fields,
            stock_list=list(codes),
            period=period,
            start_time=start_time,
            end_time=end_time,
            dividend_type=dividend_type,
            fill_data=True,
        )
    else:
        raw = xtdata.get_market_data(
            field_list=fields,
            stock_list=list(codes),
            period=period,
            start_time=start_time,
            end_time=end_time,
            dividend_type=dividend_type,
        )
    out = {}
    if isinstance(raw, dict) and codes:
        sample = raw.get(codes[0])
        if hasattr(sample, "to_json"):
            for k, v in raw.items():
                payload = _df_to_split(v)
                if payload:
                    out[k] = payload
        elif isinstance(raw, dict) and "close" in raw:
            close_df = raw["close"]
            if hasattr(close_df, "columns"):
                for code in close_df.columns:
                    rows = {}
                    index = list(getattr(close_df, "index", []))
                    rows["index"] = [str(x) for x in index]
                    rows["columns"] = []
                    rows["data"] = []
                    cols = {}
                    for field, df in raw.items():
                        if hasattr(df, "columns") and code in df.columns:
                            col = field.lower().replace("preclose", "pre_close")
                            cols[col] = [df[code].iloc[i] for i in range(len(df.index))]
                    if cols:
                        rows["columns"] = sorted(cols.keys())
                        for i in range(len(index)):
                            rows["data"].append([cols[c][i] for c in rows["columns"]])
                        out[code] = json.dumps(rows)
    return {"bars": out}


def _cmd_download_financial(xtdata, params):
    _ensure_connect(xtdata)
    codes = params.get("codes") or []
    tables = params.get("tables") or []
    try:
        if hasattr(xtdata, "download_financial_data2"):
            xtdata.download_financial_data2(list(codes), list(tables))
            return {"success": len(codes), "failed": 0, "failed_codes": []}
        ok = 0
        for code in codes:
            xtdata.download_financial_data(code, list(tables))
            ok += 1
        return {"success": ok, "failed": 0, "failed_codes": []}
    except Exception:
        return {"success": 0, "failed": len(codes), "failed_codes": list(codes)}


def _cmd_get_financial(xtdata, params):
    _ensure_connect(xtdata)
    raw = xtdata.get_financial_data(
        stock_list=list(params.get("codes") or []),
        table_list=list(params.get("tables") or []),
        start_time=params.get("start_time", ""),
        end_time=params.get("end_time", ""),
        report_type=params.get("report_type", "report_time"),
    )
    out = {}
    if isinstance(raw, dict):
        for code, tables in raw.items():
            out[code] = {}
            if isinstance(tables, dict):
                for tname, df in tables.items():
                    out[code][tname] = _df_to_split(df)
    return {"financial": out}


def _cmd_ping(xtdata, params):
    _ensure_connect(xtdata)
    codes = xtdata.get_stock_list_in_sector(params.get("sector", "沪深A股"))
    return {"ok": True, "sector_count": len(codes or []), "sample": list(codes or [])[:3]}


def _cmd_probe_port(xtdata, params):
    port = int(params.get("port", 58610))
    _ensure_connect(xtdata, port_override=port)
    xtdata.get_market_data_ex(
        field_list=["close"],
        stock_list=["600519.SH"],
        period="1d",
        count=1,
        dividend_type="front",
        fill_data=True,
    )
    return {"port": port, "data_ok": True}


def _cmd_get_trading_dates(xtdata, params):
    _ensure_connect(xtdata)
    market = params.get("market", "SH")
    start_time = params.get("start_time", "")
    end_time = params.get("end_time", "")
    dates = []
    if hasattr(xtdata, "get_trading_dates"):
        try:
            raw = xtdata.get_trading_dates(market, start_time, end_time)
            for d in raw or []:
                s = str(d).replace("-", "")[:8]
                if len(s) == 8:
                    dates.append("%s-%s-%s" % (s[:4], s[4:6], s[6:8]))
        except Exception:
            dates = []
    if not dates:
        ref = "000001.SH" if market.upper() in ("SH", "SSE", "") else "399001.SZ"
        bars = _cmd_get_market_bars(
            xtdata,
            {
                "codes": [ref],
                "period": "1d",
                "start_time": start_time,
                "end_time": end_time,
                "dividend_type": "none",
            },
        )
        payload = (bars.get("bars") or {}).get(ref)
        if payload:
            obj = json.loads(payload) if isinstance(payload, str) else payload
            for idx in obj.get("index") or []:
                dates.append(str(idx)[:10])
    return {"dates": sorted(set(dates))}


HANDLERS = {
    "ping": _cmd_ping,
    "probe_port": _cmd_probe_port,
    "get_sector_stocks": _cmd_get_sector_stocks,
    "get_instrument_detail": _cmd_get_instrument_detail,
    "download_history": _cmd_download_history,
    "get_market_bars": _cmd_get_market_bars,
    "download_financial": _cmd_download_financial,
    "get_financial": _cmd_get_financial,
    "get_trading_dates": _cmd_get_trading_dates,
}


def _emit(payload, exit_code=0):
    out_path = os.environ.get("XT_WORKER_OUTPUT")
    text = json.dumps(payload, ensure_ascii=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    return exit_code


def main():
    _bootstrap_import_path()
    xt_path = os.environ.get("XTQUANT_SITE_PACKAGES", "")
    if xt_path and xt_path not in sys.path:
        sys.path.insert(0, xt_path)
    try:
        from xtquant import xtdata
    except Exception as exc:
        return _emit({"ok": False, "error": "import xtquant failed: %s" % exc}, 1)

    try:
        if hasattr(sys.stdin, "buffer"):
            raw = sys.stdin.buffer.read().decode("utf-8")
        else:
            raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
        cmd = payload.get("cmd")
        params = payload.get("params") or {}
        handler = HANDLERS.get(cmd)
        if not handler:
            return _emit({"ok": False, "error": "unknown cmd: %s" % cmd}, 1)
        result = handler(xtdata, params)
        return _emit({"ok": True, "result": result}, 0)
    except Exception:
        return _emit({"ok": False, "error": traceback.format_exc()}, 1)


if __name__ == "__main__":
    sys.exit(main())
