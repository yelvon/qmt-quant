"""SQLite database helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, List, Optional, Sequence, Tuple

from qmt_quant.config import ROOT_DIR, get_settings

MIGRATIONS_DIR = ROOT_DIR / "migrations"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_file
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_migrations(db_path: Optional[Path] = None) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = sql_file.name
            row = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
            if row:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
            )


def executemany(
    conn: sqlite3.Connection,
    sql: str,
    rows: Iterable[Sequence[Any]],
) -> int:
    cur = conn.executemany(sql, list(rows))
    return cur.rowcount


def fetch_all(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def fetch_one(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
    return conn.execute(sql, params).fetchone()
