"""PostgreSQL concurrency smoke tests."""

import threading
import time

from qmt_quant.storage.database import connect, db_session


def test_concurrent_write_and_read(db):
    errors: list[str] = []

    def writer() -> None:
        try:
            conn = connect(db)
            try:
                for i in range(100):
                    conn.execute(
                        """
                        INSERT INTO sync_meta(key, value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
                        """,
                        (f"k{i % 5}", str(i)),
                    )
                    if i % 20 == 0:
                        conn.commit()
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            errors.append(f"writer: {exc}")

    def reader() -> None:
        try:
            for _ in range(30):
                with db_session(db) as conn:
                    conn.execute("SELECT COUNT(*) FROM sync_meta").fetchone()
                time.sleep(0.01)
        except Exception as exc:
            errors.append(f"reader: {exc}")

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert not errors, errors
