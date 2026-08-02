import json
import os
import sys

sys.path.insert(0, os.environ["XTQUANT_SITE_PACKAGES"])
from xtquant import xtconn

servers = xtconn.scan_available_server_addr()
instances = xtconn.scan_all_server_instance()
out = {"servers": servers, "instances": instances}
open(os.environ.get("XT_WORKER_OUTPUT", "data/scan.json"), "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=2)
)
