"""QMT / xtquant connectivity checks before data sync."""

from __future__ import annotations

from typing import Tuple


def check_qmt_connection(sector: str = "沪深A股") -> Tuple[bool, str]:
    """Return (ok, human-readable message)."""
    try:
        from qmt_quant.adapters.qmt.runtime import ping_xtquant, should_use_x64_bridge

        if should_use_x64_bridge():
            info = ping_xtquant(sector=sector)
            if not info.get("ok"):
                return False, "QMT 数据服务未响应，请确认 MiniQMT 已登录"
            count = int(info.get("sector_count") or 0)
            if count <= 0:
                return False, f"QMT 已连接但股票池「{sector}」为空，请检查客户端状态"
            port = info.get("port", "")
            return True, f"QMT 已连接（端口 {port}，{sector} {count} 只）"

        from qmt_quant.core.doctor import ensure_xtquant_path

        ensure_xtquant_path()
        from xtquant import xtdata  # type: ignore

        if hasattr(xtdata, "connect"):
            from qmt_quant.adapters.qmt.runtime import resolve_xtquant_port

            xtdata.connect("", resolve_xtquant_port())
        codes = xtdata.get_stock_list_in_sector(sector)
        count = len(codes or [])
        if count <= 0:
            return False, f"QMT 已连接但股票池「{sector}」为空"
        return True, f"QMT 已连接（{sector} {count} 只）"
    except Exception as exc:
        return False, f"QMT 未就绪：{exc}"


def ensure_qmt_ready(sector: str = "沪深A股") -> None:
    ok, msg = check_qmt_connection(sector)
    if not ok:
        raise RuntimeError(msg)
