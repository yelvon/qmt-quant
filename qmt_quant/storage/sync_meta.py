"""Sync metadata / watermarks."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO sync_meta(key, value, updated_at) VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (key, value),
    )


def get_meta_json(conn: sqlite3.Connection, key: str) -> Optional[Dict[str, Any]]:
    raw = get_meta(conn, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_meta_json(conn: sqlite3.Connection, key: str, payload: Dict[str, Any]) -> None:
    set_meta(conn, key, json.dumps(payload, ensure_ascii=False))
