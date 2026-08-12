"""PostgreSQL database helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterable, List, Optional, Sequence, Tuple

import psycopg
from psycopg import Connection
from psycopg.rows import tuple_row

from qmt_quant.config import ROOT_DIR, get_settings

MIGRATIONS_DIR = ROOT_DIR / "migrations"

DbConnection = Connection[tuple]


def get_database_url(override: Optional[str] = None) -> str:
    if override:
        return override
    return get_settings().database_url


def connect(dsn: Optional[str] = None) -> DbConnection:
    url = get_database_url(dsn)
    if not url:
        raise RuntimeError(
            "DATABASE_URL / data.db_url is not configured. "
            "Start PostgreSQL (docker compose up -d) and set DATABASE_URL."
        )
    return psycopg.connect(url, row_factory=tuple_row)


@contextmanager
def db_session(dsn: Optional[str] = None) -> Generator[DbConnection, None, None]:
    conn = connect(dsn)
    try:
        yield conn
        from qmt_quant.storage.db_retry import run_db_retry

        run_db_retry(conn.commit)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _split_sql(script: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if ";" in line:
            chunk = "\n".join(buf)
            for stmt in chunk.split(";"):
                stmt = stmt.strip()
                if stmt:
                    parts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def run_migrations(dsn: Optional[str] = None) -> None:
    with db_session(dsn) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = sql_file.name
            row = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
            if row:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            for stmt in _split_sql(sql):
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s)",
                (version,),
            )


def executemany(
    conn: DbConnection,
    sql: str,
    rows: Iterable[Sequence[Any]],
) -> int:
    data = list(rows)
    if not data:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, data)
        return cur.rowcount


def fetch_all(
    conn: DbConnection, sql: str, params: Tuple[Any, ...] = ()
) -> List[tuple]:
    return list(conn.execute(sql, params).fetchall())


def fetch_one(
    conn: DbConnection, sql: str, params: Tuple[Any, ...] = ()
) -> Optional[tuple]:
    return conn.execute(sql, params).fetchone()


def row_to_dict(conn: DbConnection, sql: str, params: Tuple[Any, ...] = ()) -> Optional[dict]:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    names = [desc.name for desc in cur.description]
    return dict(zip(names, row))


def rows_to_dicts(conn: DbConnection, sql: str, params: Tuple[Any, ...] = ()) -> List[dict]:
    cur = conn.execute(sql, params)
    names = [desc.name for desc in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def ping_database(dsn: Optional[str] = None) -> Tuple[bool, str]:
    try:
        with db_session(dsn) as conn:
            conn.execute("SELECT 1")
        return True, "PostgreSQL connection ok"
    except Exception as exc:
        return False, f"PostgreSQL unavailable: {exc}"
