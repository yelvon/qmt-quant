"""Financial statement sync."""

from __future__ import annotations

from typing import Dict, List, Sequence

from qmt_quant.adapters.qmt.client import XtDataClient
from qmt_quant.adapters.qmt.transform import financial_rows_from_frame
from qmt_quant.core.sync.universe import resolve_universe
from qmt_quant.storage.database import db_session, run_migrations
from qmt_quant.storage.financial import upsert_financial


def sync_financial(
    *,
    sector: str = "沪深A股",
    tables: Sequence[str] | None = None,
) -> Dict[str, object]:
    run_migrations()
    table_list = list(tables or ["Balance", "Income", "CashFlow", "Pershareindex"])
    codes = resolve_universe(sector)
    client = XtDataClient()
    client.download_financial(codes, table_list)
    data = client.get_financial_data(codes, table_list)

    written = 0
    with db_session() as conn:
        for code, tables_data in data.items():
            for table_name, df in tables_data.items():
                if table_name not in table_list:
                    continue
                for _, report_date, announce_date, payload in financial_rows_from_frame(
                    code, table_name, df
                ):
                    upsert_financial(conn, table_name, code, report_date, announce_date, payload)
                    written += 1
    return {"sector": sector, "tables": table_list, "codes": len(codes), "rows_written": written}
