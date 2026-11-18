"""The directory's only table: who is in the network and where. No medicine data, ever."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    org_id TEXT PRIMARY KEY,
    org_type TEXT NOT NULL,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    issuer_code TEXT UNIQUE,
    gs1_prefix TEXT,
    base_url TEXT NOT NULL,
    public_key TEXT NOT NULL,
    host_name TEXT NOT NULL,
    registered_at REAL NOT NULL,
    last_seen REAL NOT NULL
)
"""

FIELDS = (
    "org_id", "org_type", "name", "city", "state", "issuer_code", "gs1_prefix",
    "base_url", "public_key", "host_name",
)  # fmt: skip


class Store:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "directory.sqlite"
        with self._conn() as c:
            c.execute(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def get(self, org_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
        return dict(row) if row else None

    def upsert(self, org: dict[str, Any], now: float) -> bool:
        """Insert or update; returns True when the org is new."""
        existing = self.get(org["org_id"])
        values = [org.get(f) for f in FIELDS]
        with self._conn() as c:
            if existing is None:
                c.execute(
                    f"INSERT INTO orgs ({', '.join(FIELDS)}, registered_at, last_seen) "
                    f"VALUES ({', '.join('?' * len(FIELDS))}, ?, ?)",
                    (*values, now, now),
                )
                return True
            sets = ", ".join(f"{f} = ?" for f in FIELDS[1:])
            c.execute(f"UPDATE orgs SET {sets}, last_seen = ? WHERE org_id = ?", (*values[1:], now, org["org_id"]))
            return False

    def touch(self, org_id: str, now: float) -> None:
        with self._conn() as c:
            c.execute("UPDATE orgs SET last_seen = ? WHERE org_id = ?", (now, org_id))

    def list(self, org_type: str | None = None, state: str | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM orgs WHERE 1 = 1", []
        if org_type:
            sql, args = sql + " AND org_type = ?", [*args, org_type]
        if state:
            sql, args = sql + " AND state = ?", [*args, state]
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql + " ORDER BY org_id", args)]

    def by_issuer(self, code: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM orgs WHERE issuer_code = ?", (code,)).fetchone()
        return dict(row) if row else None

    def by_gtin(self, gtin: str) -> dict[str, Any] | None:
        """Longest GS1 company prefix that the GTIN (after its indicator digit) starts with."""
        body = gtin[1:]
        matches = [o for o in self.list() if o["gs1_prefix"] and body.startswith(o["gs1_prefix"])]
        return max(matches, key=lambda o: len(o["gs1_prefix"]), default=None)
