# Linux smoke verification (no QMT)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== doctor =="
python -m qmt_quant.cli.main doctor || true

echo "== init-db =="
python -m qmt_quant.cli.main init-db

echo "== pytest =="
python -m pytest tests/ -q --ignore=tests/test_nautilus_engine.py::test_nautilus_engine_smoke

echo "== API import =="
python -c "from qmt_quant.web.app import create_app; create_app(); print('OK')"

echo "Done. QMT sync steps skipped on Linux — see docs/windows-e2e.md"
