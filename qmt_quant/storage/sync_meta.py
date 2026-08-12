"""Sync metadata / watermarks."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from qmt_quant.storage.database import DbConnection


def get_meta(conn: DbConnection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM sync_meta WHERE key = %s", (key,)).fetchone()
    return row[0] if row else None


def set_meta(conn: DbConnection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO sync_meta(key, value, updated_at) VALUES (%s, %s, NOW())
        ON CONFLICT(key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = NOW()
        """,
        (key, value),
    )


def get_meta_json(conn: DbConnection, key: str) -> Optional[Dict[str, Any]]:
    raw = get_meta(conn, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_meta_json(conn: DbConnection, key: str, payload: Dict[str, Any]) -> None:
    set_meta(conn, key, json.dumps(payload, ensure_ascii=False))
