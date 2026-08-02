import json
import os
import sys

sys.path.insert(0, os.environ["XTQUANT_SITE_PACKAGES"])
out = os.environ.get("XT_WORKER_OUTPUT", "data/xtdc_test.json")

try:
    from xtquant import xtdatacenter as xtdc

    home = os.environ.get("QMT_DATA_HOME", "")
    if home:
        xtdc.set_data_home_dir(home)
    xtdc.init(start_local_service=True)
    payload = {"ok": True, "port": xtdc.get_local_server_port()}
except Exception as exc:
    payload = {"ok": False, "error": repr(exc)}

open(out, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
