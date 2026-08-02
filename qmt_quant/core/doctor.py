"""Environment and QMT health checks."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from qmt_quant.config import ROOT_DIR, get_settings


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


@dataclass
class DoctorReport:
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def _discover_xtquant_path(install_dir: Path) -> Optional[Path]:
    candidates = [
        install_dir / "bin.x64" / "Lib" / "site-packages",
        install_dir / "python" / "Lib" / "site-packages",
    ]
    for base in [install_dir] + list(install_dir.glob("*")):
        if base.is_dir():
            candidates.extend([
                base / "bin.x64" / "Lib" / "site-packages",
                base / "python" / "Lib" / "site-packages",
            ])
    for p in candidates:
        if (p / "xtquant").exists():
            return p
    return None


def ensure_xtquant_path() -> Optional[str]:
    settings = get_settings()
    if settings.xtquant_site_packages and Path(settings.xtquant_site_packages).exists():
        path = settings.xtquant_site_packages
    else:
        found = _discover_xtquant_path(Path(settings.qmt_install_dir))
        path = str(found) if found else None
    if path and path not in sys.path:
        sys.path.insert(0, path)
    return path


def run_doctor() -> DoctorReport:
    settings = get_settings()
    report = DoctorReport()

    py_ver = sys.version_info
    report.checks.append(
        CheckResult(
            "python_version",
            py_ver >= (3, 10),
            f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}",
        )
    )

    qmt_dir = Path(settings.qmt_install_dir)
    report.checks.append(
        CheckResult(
            "qmt_install_dir",
            qmt_dir.exists(),
            str(qmt_dir),
        )
    )

    xt_path = ensure_xtquant_path()
    xt_ok = False
    xt_msg = "xtquant not configured"
    try:
        from qmt_quant.adapters.qmt.runtime import ping_xtquant, should_use_x64_bridge

        if should_use_x64_bridge():
            info = ping_xtquant()
            xt_ok = bool(info.get("ok"))
            port = info.get("port", get_settings().xtquant_port)
            xt_msg = (
                f"xtquant bridge ok via x64 Python "
                f"(port={port}, sector={info.get('sector_count', 0)})"
            )
        else:
            if xt_path:
                import xtquant  # noqa: F401
                xt_ok = True
                xt_msg = f"xtquant import ok ({xt_path})"
            else:
                import xtquant  # noqa: F401
                xt_ok = True
                xt_msg = "xtquant import ok (pip)"
    except Exception as exc:
        xt_msg = f"xtquant failed: {exc}"
    report.checks.append(CheckResult("xtquant", xt_ok, xt_msg))

    db_parent = settings.db_file.parent
    db_parent.mkdir(parents=True, exist_ok=True)
    writable = os.access(db_parent, os.W_OK)
    report.checks.append(
        CheckResult("data_dir_writable", writable, str(db_parent))
    )

    catalog_dir = settings.catalog_dir
    catalog_dir.mkdir(parents=True, exist_ok=True)
    report.checks.append(
        CheckResult(
            "catalog_dir",
            catalog_dir.exists(),
            str(catalog_dir),
        )
    )

    migrations = ROOT_DIR / "migrations" / "001_init.sql"
    report.checks.append(
        CheckResult("migrations", migrations.exists(), str(migrations))
    )

    if settings.quant_python:
        report.checks.append(
            CheckResult(
                "quant_python_configured",
                Path(settings.quant_python).exists(),
                settings.quant_python,
            )
        )

    qmt_py_ok = bool(settings.qmt_python) and Path(settings.qmt_python).exists()
    if not qmt_py_ok:
        report.checks.append(
            CheckResult(
                "qmt_python_for_jobs",
                False,
                "WARN: qmt_python not configured — QMT sync jobs may run in quant-env instead of qmt-env",
            )
        )
    else:
        report.checks.append(
            CheckResult(
                "qmt_python_for_jobs",
                True,
                settings.qmt_python,
            )
        )

    return report
