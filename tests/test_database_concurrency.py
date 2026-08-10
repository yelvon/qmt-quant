"""SQLite concurrency helpers."""

import threading
import time

from qmt_quant.storage.database import connect, db_session, run_migrations


def test_wal_mode_enabled(tmp_path, monkeypatch):
    db_file = tmp_path / "wal.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)

    conn = connect(db_file)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
    finally:
        conn.close()


def test_concurrent_write_and_read(tmp_path, monkeypatch):
    db_file = tmp_path / "concurrent.db"
    monkeypatch.setenv("QMT_QUANT_DB", str(db_file))
    from qmt_quant import config

    config._settings = None
    run_migrations(db_file)

    errors: list[str] = []

    def writer() -> None:
        try:
            conn = connect(db_file)
            try:
                for i in range(200):
                    conn.execute(
                        """
                        INSERT INTO sync_meta(key, value, updated_at)
                        VALUES (?, ?, datetime('now'))
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value
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
            for _ in range(50):
                with db_session(db_file) as conn:
                    conn.execute("SELECT COUNT(*) FROM sync_meta").fetchone()
                time.sleep(0.01)
        except Exception as exc:
            errors.append(f"reader: {exc}")

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, errors
