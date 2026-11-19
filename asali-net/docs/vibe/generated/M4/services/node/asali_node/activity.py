"""The portal's own audit trail: who did what and when. Kept in a small local SQLite file, not in the org's data."""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from asali_node.canonical import IST


class ActivityLog:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(data_dir / "activity.sqlite", check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, "
            "action TEXT NOT NULL, detail TEXT NOT NULL)"
        )

    def add(self, actor: str, action: str, detail: str, at: datetime | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO activity (at, actor, action, detail) VALUES (?, ?, ?, ?)",
                ((at or datetime.now(IST)).isoformat(), actor, action, detail),
            )
            self._conn.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT at, actor, action, detail FROM activity ORDER BY at DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"at": a, "actor": b, "action": c, "detail": d} for a, b, c, d in rows]
