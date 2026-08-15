"""Financial sync cancellation tests."""

from unittest.mock import MagicMock, patch

import pytest

from qmt_quant.core.jobs.context import JobCancelled, request_job_cancel
from qmt_quant.storage.database import db_session
from qmt_quant.storage.jobs import create_job, update_job


def test_sync_financial_raises_on_cancel(db):
    from qmt_quant.core.sync.financial import sync_financial

    with db_session(db) as conn:
        job_id = create_job(
            conn,
            display_name="同步财报",
            job_type="sync_financial",
            env="qmt",
            params={},
        )
        update_job(conn, job_id, status="running")

    request_job_cancel(job_id)

    client = MagicMock()
    client.download_financial.return_value = MagicMock(success=2, failed=0, failed_codes=[])
    client.get_financial_data.return_value = {}

    with patch("qmt_quant.core.sync.financial.XtDataClient", return_value=client):
        with patch("qmt_quant.core.sync.financial.resolve_universe", return_value=["600519.SH", "000001.SZ"]):
            with patch("qmt_quant.core.sync.financial.get_settings") as mock_settings:
                mock_settings.return_value.sync_batch_size = 1
                with pytest.raises(JobCancelled) as exc:
                    sync_financial(sector="沪深A股", incremental=False, job_id=job_id)
    assert exc.value.checkpoint["total"] == 2
    assert len(exc.value.checkpoint["remaining_codes"]) == 2
