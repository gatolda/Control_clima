"""Cola persistente en SQLite para no perder telemetria si no hay red.

Diseño:
- Cada item se guarda como JSON con su tipo (telemetry | actuator | irrigation)
- El loop del agente lee en batches y los elimina al publicar con exito
- Si la API responde error, los items quedan en la cola y se reintenta despues
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_outbox_kind ON outbox(kind);
"""


class PersistentQueue:
    """Cola thread-safe respaldada por SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def enqueue(self, kind: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO outbox (kind, payload) VALUES (?, ?)",
                (kind, json.dumps(payload)),
            )
            conn.commit()

    def peek(self, kind: str, limit: int = 100) -> list[tuple[int, dict[str, Any]]]:
        """Retorna [(id, payload), ...] sin eliminar."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, payload FROM outbox WHERE kind = ? ORDER BY id ASC LIMIT ?",
                (kind, limit),
            ).fetchall()
        return [(row[0], json.loads(row[1])) for row in rows]

    def delete(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._lock, self._connect() as conn:
            conn.execute(f"DELETE FROM outbox WHERE id IN ({placeholders})", ids)
            conn.commit()

    def size(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()
        return int(row[0])

    def trim(self, max_size: int) -> int:
        """Si la cola excede max_size, elimina los items mas antiguos."""
        current = self.size()
        if current <= max_size:
            return 0
        to_remove = current - max_size
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM outbox WHERE id IN (SELECT id FROM outbox ORDER BY id ASC LIMIT ?)",
                (to_remove,),
            )
            conn.commit()
        return to_remove
