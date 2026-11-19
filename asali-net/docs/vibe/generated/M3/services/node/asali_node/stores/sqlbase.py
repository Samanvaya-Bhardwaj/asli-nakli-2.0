"""Small helper shared by the SQL adapters: one tiny API over SQLite and PostgreSQL.

SQL is written with ``?`` placeholders; this turns them into ``%s`` for PostgreSQL. Datetimes
go to PostgreSQL as timezone-aware values and to SQLite as ISO text. Nothing else is hidden.
"""

import re
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from asali_node.canonical import IST
from asali_node.stores import engines

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"


def to_ist(v: Any) -> datetime:
    """Accept what an engine hands back and return an IST-aware datetime."""
    if isinstance(v, datetime):
        return v.astimezone(IST) if v.tzinfo else v.replace(tzinfo=IST)
    if isinstance(v, str):
        d = datetime.fromisoformat(v)
        return d.astimezone(IST) if d.tzinfo else d.replace(tzinfo=IST)
    raise ValueError(f"not a datetime: {v!r}")


def to_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


class Tx:
    def __init__(self, cur: Any, kind: str):
        self._cur, self._kind = cur, kind

    def _prep(self, sql: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
        if self._kind == "sqlite":
            out: list[Any] = []
            for p in params:
                if isinstance(p, datetime):
                    out.append(p.astimezone(IST).isoformat())
                elif isinstance(p, date):
                    out.append(p.isoformat())
                else:
                    out.append(p)
            return sql, tuple(out)
        return sql.replace("?", "%s"), params

    def run(self, sql: str, *params: Any) -> None:
        s, p = self._prep(sql, params)
        self._cur.execute(s, p)

    def rows(self, sql: str, *params: Any) -> list[tuple[Any, ...]]:
        s, p = self._prep(sql, params)
        self._cur.execute(s, p)
        return [tuple(r) for r in self._cur.fetchall()]


class SqlDb:
    def __init__(self, kind: str, target: str, mode: str):
        self.kind, self.ro = kind, mode == "ro"
        self._lock = threading.RLock()
        if kind == "sqlite":
            self._conn = engines.sqlite_conn(target, self.ro)
        else:
            self._pool = engines.pg_pool(target)

    @contextmanager
    def tx(self) -> Iterator[Tx]:
        if self.kind == "sqlite":
            with self._lock:
                cur = self._conn.cursor()
                try:
                    yield Tx(cur, "sqlite")
                    self._conn.commit()
                except BaseException:
                    self._conn.rollback()
                    raise
                finally:
                    cur.close()
        else:
            with self._pool.connection() as conn, conn.cursor() as cur:
                yield Tx(cur, "pg")

    def rows(self, sql: str, *params: Any) -> list[tuple[Any, ...]]:
        with self.tx() as t:
            return t.rows(sql, *params)

    def run(self, sql: str, *params: Any) -> None:
        with self.tx() as t:
            t.run(sql, *params)

    def script(self, org_id: str) -> None:
        """Create the org's tables if they are missing (read-write mode only)."""
        text = (SCHEMAS / org_id / "schema.sql").read_text(encoding="utf-8")
        statements = [s.strip() for s in re.split(r";\s*(?:\n|$)", text) if s.strip()]
        with self.tx() as t:
            for s in statements:
                t.run(s)

    def close(self) -> None:
        if self.kind == "sqlite":
            self._conn.close()
        else:
            self._pool.close()
