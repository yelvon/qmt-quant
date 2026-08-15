"""QMT xtquant runtime helpers (ARM64 -> x64 bridge)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from qmt_quant.config import ROOT_DIR, get_settings


def is_arm64_python() -> bool:
    return platform.machine().upper() in ("ARM64", "AARCH64")


def _bridge_python_candidates() -> List[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    names = (
        "Python311/python.exe",
        "Python312/python.exe",
        "Python310/python.exe",
        "Python311-32/python.exe",
    )
    out: List[Path] = []
    for name in names:
        p = local / name
        if p not in out:
            out.append(p)
    return out


def resolve_qmt_terminal_dir() -> Optional[Path]:
    settings = get_settings()
    base = Path(settings.qmt_install_dir)
    if not base.exists():
        return None
    configured = settings.qmt_python.strip()
    if configured:
        parent = Path(configured).resolve().parent
        if parent.name == "bin.x64" and parent.parent.exists():
            return parent.parent
    for child in base.iterdir():
        if child.is_dir() and "QMT" in child.name.upper():
            return child
    return base


@lru_cache(maxsize=1)
def resolve_bridge_python() -> Optional[Path]:
    """x64 Python with xtquant for subprocess bridge (preferred over QMT pythonw)."""
    settings = get_settings()
    candidates: List[Path] = []
    if settings.qmt_python:
        candidates.append(Path(settings.qmt_python))
    candidates.extend(_bridge_python_candidates())
    term = resolve_qmt_terminal_dir()
    if term:
        candidates.append(term / "bin.x64" / "pythonw.exe")
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        if _python_can_import_xtquant(path):
            return path
    return None


def _python_site_packages(python_exe: Path) -> Optional[Path]:
    if python_exe.name.lower() == "pythonw.exe":
        return None
    sp = python_exe.resolve().parent / "Lib" / "site-packages"
    return sp if (sp / "xtquant").exists() else None


def _python_can_import_xtquant(python_exe: Path) -> bool:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE")
    }
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    sp = _python_site_packages(python_exe)
    if sp:
        env["XTQUANT_SITE_PACKAGES"] = str(sp)
    script = (
        "import sys\n"
        "try:\n"
        " from xtquant import xtdata\n"
        " print('ok')\n"
        "except Exception as e:\n"
        " print('fail', e)\n"
        " sys.exit(1)\n"
    )
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and "ok" in (proc.stdout or "")


def default_xtquant_site_packages() -> Optional[Path]:
    settings = get_settings()
    if settings.qmt_python:
        sp = _python_site_packages(Path(settings.qmt_python))
        if sp:
            return sp
    if settings.xtquant_site_packages:
        p = Path(settings.xtquant_site_packages)
        if (p / "xtquant").exists() or p.name == "xtquant":
            return p if p.name != "xtquant" else p.parent
    for candidate in _bridge_python_candidates():
        sp = _python_site_packages(candidate)
        if sp:
            return sp
    candidate = Path(sys.prefix) / "Lib" / "site-packages"
    if (candidate / "xtquant").exists():
        return candidate
    return None


def resolve_qmt_pythonw() -> Optional[Path]:
    """Backward-compatible alias for bridge Python executable."""
    return resolve_bridge_python()


def _sanitized_bridge_env() -> Dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE")
    }
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    xt_pkg = default_xtquant_site_packages()
    if xt_pkg:
        env["XTQUANT_SITE_PACKAGES"] = str(xt_pkg)
    term = resolve_qmt_terminal_dir()
    if term:
        env["QMT_DATA_HOME"] = str(term)
    env.setdefault("QMT_XTQUANT_PORT", str(resolve_xtquant_port()))
    return env


@lru_cache(maxsize=1)
def should_use_x64_bridge() -> bool:
    bridge = resolve_bridge_python()
    if bridge is None:
        return False
    if is_arm64_python():
        return True
    try:
        xt_pkg = default_xtquant_site_packages()
        if xt_pkg and str(xt_pkg) not in sys.path:
            sys.path.insert(0, str(xt_pkg))
        from xtquant import xtdata  # noqa: F401
        return False
    except Exception:
        return True


_RESOLVED_XTQUANT_PORT: Optional[int] = None
def resolve_xtquant_port() -> int:
    """Use configured MiniQMT port; auto-probe only when unset."""
    global _RESOLVED_XTQUANT_PORT
    if _RESOLVED_XTQUANT_PORT is not None:
        return _RESOLVED_XTQUANT_PORT
    settings = get_settings()
    if settings.xtquant_port:
        _RESOLVED_XTQUANT_PORT = int(settings.xtquant_port)
        return _RESOLVED_XTQUANT_PORT
    preferred: List[int] = [58610, 58609, 58601, 58600]
    if not should_use_x64_bridge():
        _RESOLVED_XTQUANT_PORT = preferred[0]
        return _RESOLVED_XTQUANT_PORT
    for port in preferred:
        if _probe_data_port(port):
            _RESOLVED_XTQUANT_PORT = port
            return port
    _RESOLVED_XTQUANT_PORT = preferred[0]
    return _RESOLVED_XTQUANT_PORT


def _probe_data_port(port: int) -> bool:
    try:
        result = _run_xt_worker("probe_port", {"port": port}, port_override=port)
        return bool(result.get("data_ok"))
    except Exception:
        return False


def _run_xt_worker(
    cmd: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    port_override: Optional[int] = None,
) -> Dict[str, Any]:
    import tempfile

    py = resolve_bridge_python()
    xt_pkg = default_xtquant_site_packages()
    if not py:
        raise RuntimeError("QMT x64 bridge not configured (install Python 3.11 x64 + xtquant)")
    worker = ROOT_DIR / "scripts" / "xtdata_worker.py"
    env = _sanitized_bridge_env()
    if xt_pkg:
        env["XTQUANT_SITE_PACKAGES"] = str(xt_pkg)
    if port_override is not None:
        env["QMT_XTQUANT_PORT"] = str(port_override)
    elif _RESOLVED_XTQUANT_PORT is not None:
        env["QMT_XTQUANT_PORT"] = str(_RESOLVED_XTQUANT_PORT)
    else:
        env["QMT_XTQUANT_PORT"] = str(get_settings().xtquant_port or 58610)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        out_path = tf.name
    env["XT_WORKER_OUTPUT"] = out_path
    payload = json.dumps({"cmd": cmd, "params": params or {}}, ensure_ascii=False)
    timeout = 30 if cmd == "probe_port" else 600
    proc = subprocess.run(
        [str(py), str(worker)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
        timeout=timeout,
    )
    try:
        raw = Path(out_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RuntimeError(proc.stderr or proc.stdout or f"xt worker produced no output: {cmd}")
    finally:
        Path(out_path).unlink(missing_ok=True)
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(raw or proc.stderr or f"invalid worker output for {cmd}") from exc
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or f"xt worker error: {cmd}")
    return data.get("result") or {}


def ping_xtquant(sector: str = "沪深A股") -> Dict[str, Any]:
    if should_use_x64_bridge():
        port = resolve_xtquant_port()
        info = _run_xt_worker("ping", {"sector": sector})
        info["port"] = port
        return info
    from xtquant import xtdata  # type: ignore

    if hasattr(xtdata, "connect"):
        xtdata.connect("", resolve_xtquant_port())
    codes = xtdata.get_stock_list_in_sector(sector)
    return {"ok": True, "sector_count": len(codes or []), "sample": list(codes or [])[:3]}


def _json_to_df(payload: str) -> pd.DataFrame:
    obj = json.loads(payload)
    df = pd.DataFrame(obj["data"], columns=obj["columns"], index=obj["index"])
    df.index = pd.to_datetime(df.index)
    return df


class XtDataBridgeClient:
    """Subprocess xtdata client via x64 Python bridge."""

    def get_sector_stocks(self, sector: str) -> List[str]:
        result = _run_xt_worker("get_sector_stocks", {"sector": sector})
        return [str(c) for c in result.get("codes") or []]

    def get_instrument_detail(self, code: str) -> Dict[str, Any]:
        result = _run_xt_worker("get_instrument_detail", {"code": code})
        return result.get("detail") or {}

    def download_history(
        self,
        codes: List[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
    ) -> Dict[str, Any]:
        return _run_xt_worker(
            "download_history",
            {
                "codes": list(codes),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def get_market_bars(
        self,
        codes: List[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "front",
    ) -> Dict[str, pd.DataFrame]:
        result = _run_xt_worker(
            "get_market_bars",
            {
                "codes": list(codes),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "dividend_type": dividend_type,
            },
        )
        out: Dict[str, pd.DataFrame] = {}
        for code, payload in (result.get("bars") or {}).items():
            out[code] = _json_to_df(payload)
        return out

    def fetch_market_bars(
        self,
        codes: List[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "front",
    ) -> Dict[str, pd.DataFrame]:
        """Download + read bars in one worker subprocess."""
        result = _run_xt_worker(
            "fetch_market_bars",
            {
                "codes": list(codes),
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
                "dividend_type": dividend_type,
            },
        )
        out: Dict[str, pd.DataFrame] = {}
        for code, payload in (result.get("bars") or {}).items():
            out[code] = _json_to_df(payload)
        return out

    def download_financial(self, codes: List[str], table_list: List[str]) -> Dict[str, Any]:
        return _run_xt_worker(
            "download_financial",
            {"codes": list(codes), "tables": list(table_list)},
        )

    def get_financial_data(
        self,
        codes: List[str],
        table_list: List[str],
        start_time: str = "",
        end_time: str = "",
        report_type: str = "report_time",
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        result = _run_xt_worker(
            "get_financial",
            {
                "codes": list(codes),
                "tables": list(table_list),
                "start_time": start_time,
                "end_time": end_time,
                "report_type": report_type,
            },
        )
        out: Dict[str, Dict[str, pd.DataFrame]] = {}
        for code, tables in (result.get("financial") or {}).items():
            out[code] = {}
            for tname, payload in (tables or {}).items():
                if payload:
                    out[code][tname] = _json_to_df(payload)
        return out

    def fetch_financial_data(
        self,
        codes: List[str],
        table_list: List[str],
        start_time: str = "",
        end_time: str = "",
        report_type: str = "report_time",
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        result = _run_xt_worker(
            "fetch_financial",
            {
                "codes": list(codes),
                "tables": list(table_list),
                "start_time": start_time,
                "end_time": end_time,
                "report_type": report_type,
            },
        )
        out: Dict[str, Dict[str, pd.DataFrame]] = {}
        for code, tables in (result.get("financial") or {}).items():
            out[code] = {}
            for tname, payload in (tables or {}).items():
                if payload:
                    out[code][tname] = _json_to_df(payload)
        return out

    def get_trading_dates(
        self,
        market: str = "SH",
        start_time: str = "",
        end_time: str = "",
    ) -> List[str]:
        result = _run_xt_worker(
            "get_trading_dates",
            {"market": market, "start_time": start_time, "end_time": end_time},
        )
        return [str(d) for d in (result.get("dates") or [])]
