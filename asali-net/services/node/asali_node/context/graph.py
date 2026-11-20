"""A database seen as a graph: tables are nodes, foreign keys (or declared document references) are edges.

SqlGraph reads the keys from the database itself (PRAGMA foreign_key_list on SQLite, pg_constraint on
PostgreSQL), so nothing about an organisation's schema is written down here. MongoGraph has no foreign keys to
read, so each MongoDB store declares its references (a field of one collection holding the _id of another).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

ROW_CAP = 5000  # rows read from one table to profile it


@dataclass(frozen=True)
class Edge:
    child: str
    child_fields: tuple[str, ...]
    parent: str
    parent_fields: tuple[str, ...]
    kind: str = "foreign key"

    @property
    def label(self) -> str:
        return (
            f"{self.child}({', '.join(self.child_fields)}) -> {self.parent}({', '.join(self.parent_fields)})"
        )


class Graph(Protocol):
    tables: list[str]
    edges: list[Edge]

    def fields(self, table: str) -> list[str]: ...
    def key_fields(self, table: str) -> list[str]: ...
    def table_rows(self, table: str) -> list[dict[str, Any]]: ...
    def find(self, table: str, column: str, values: Sequence[Any]) -> list[dict[str, Any]]: ...
    def join(
        self, edge: Edge, from_table: str, rows: list[dict[str, Any]], cap: int
    ) -> tuple[str, list[dict[str, Any]], str, int]: ...
    def pk_dict(self, table: str, row: dict[str, Any]) -> dict[str, Any]: ...


def _chunks(items: list[Any], n: int = 400) -> Iterable[list[Any]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


class SqlGraph:
    """PostgreSQL or SQLite, read through the store's own connection (read-only for a share request)."""

    def __init__(self, db: Any, skip_tables: Iterable[str] = ()) -> None:
        self.db = db
        skip = {t.lower() for t in skip_tables}
        self._cols: dict[str, list[str]] = {}
        self._pk: dict[str, list[str]] = {}
        self._cache: dict[str, list[dict[str, Any]]] = {}
        edges = self._read_sqlite() if db.kind == "sqlite" else self._read_postgres()
        self.tables = sorted(t for t in self._cols if t.lower() not in skip)
        self.edges = [e for e in edges if e.child in self.tables and e.parent in self.tables]

    def _read_sqlite(self) -> list[Edge]:
        edges: list[Edge] = []
        for (t,) in self.db.rows(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ):
            info = self.db.rows(f'PRAGMA table_info("{t}")')
            self._cols[t] = [r[1] for r in info]
            self._pk[t] = [r[1] for r in sorted((r for r in info if r[5]), key=lambda r: r[5])]
            groups: dict[int, list[tuple[Any, ...]]] = {}
            for r in self.db.rows(f'PRAGMA foreign_key_list("{t}")'):
                groups.setdefault(r[0], []).append(r)
            for g in groups.values():
                edges.append(Edge(t, tuple(x[3] for x in g), g[0][2], tuple(x[4] for x in g)))
        return edges

    def _read_postgres(self) -> list[Edge]:
        for t, c in self.db.rows(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() ORDER BY table_name, ordinal_position"
        ):
            self._cols.setdefault(t, []).append(c)
        for t, c in self.db.rows(
            "SELECT cl.relname, a.attname FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid "
            "JOIN pg_namespace n ON n.oid = cl.relnamespace "
            "CROSS JOIN LATERAL unnest(k.conkey) WITH ORDINALITY AS u(num, ord) "
            "JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.num "
            "WHERE k.contype = 'p' AND n.nspname = current_schema() ORDER BY cl.relname, u.ord"
        ):
            self._pk.setdefault(t, []).append(c)
        by_name: dict[str, list[tuple[Any, ...]]] = {}
        for r in self.db.rows(
            "SELECT k.conname, cl.relname, fcl.relname, a.attname, fa.attname "
            "FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.conrelid JOIN pg_class fcl ON fcl.oid = k.confrelid "
            "JOIN pg_namespace n ON n.oid = cl.relnamespace "
            "CROSS JOIN LATERAL unnest(k.conkey, k.confkey) WITH ORDINALITY AS u(num, fnum, ord) "
            "JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.num "
            "JOIN pg_attribute fa ON fa.attrelid = k.confrelid AND fa.attnum = u.fnum "
            "WHERE k.contype = 'f' AND n.nspname = current_schema() ORDER BY k.conname, u.ord"
        ):
            by_name.setdefault(r[0], []).append(r)
        return [
            Edge(g[0][1], tuple(x[3] for x in g), g[0][2], tuple(x[4] for x in g)) for g in by_name.values()
        ]

    def fields(self, table: str) -> list[str]:
        return self._cols[table]

    def key_fields(self, table: str) -> list[str]:
        return self._pk.get(table, [])

    def _select(
        self, table: str, where: str = "", *params: Any, limit: int | None = None
    ) -> list[dict[str, Any]]:
        cols = self._cols[table]
        sql = f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{table}"{where}'
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(zip(cols, r, strict=True)) for r in self.db.rows(sql, *params)]

    def table_rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self._cache:
            self._cache[table] = self._select(table, limit=ROW_CAP)
        return self._cache[table]

    def find(self, table: str, column: str, values: Sequence[Any]) -> list[dict[str, Any]]:
        vals = [v for v in values if v not in (None, "")]
        out: list[dict[str, Any]] = []
        for part in _chunks(vals):
            out += self._select(table, f' WHERE "{column}" IN ({",".join("?" * len(part))})', *part)
        return out

    def join(
        self, edge: Edge, from_table: str, rows: list[dict[str, Any]], cap: int
    ) -> tuple[str, list[dict[str, Any]], str, int]:
        to_parent = edge.child == from_table
        src, dst = (
            (edge.child_fields, edge.parent_fields) if to_parent else (edge.parent_fields, edge.child_fields)
        )
        other = edge.parent if to_parent else edge.child
        wanted = {tuple(r.get(f) for f in src) for r in rows}
        wanted = {w for w in wanted if all(x not in (None, "") for x in w)}
        native = f"SELECT * FROM {other} WHERE ({', '.join(dst)}) IN <{len(wanted)} values from {from_table}>"
        if not wanted:
            return other, [], native, 0
        found: list[dict[str, Any]] = []
        if len(dst) == 1:
            found = self.find(other, dst[0], [w[0] for w in wanted])
        else:
            for w in list(wanted)[:cap]:
                found += self._select(other, " WHERE " + " AND ".join(f'"{c}" = ?' for c in dst), *w)
        return other, found[:cap], native, len(found)

    def pk_dict(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        keys = self._pk.get(table) or self._cols[table][:1]
        return {k: row.get(k) for k in keys}


def _flat(doc: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Scalars of a document, nested objects as dotted names; arrays are counted, and reached by references."""
    out: dict[str, Any] = {}
    for k, v in doc.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, name + "."))
        elif isinstance(v, list):
            out[name + ".count"] = len(v)
        elif v is not None:
            out[name] = v
    return out


class MongoGraph:
    """MongoDB: collections are nodes; references are declared by the store, as (child, field, parent, field)."""

    def __init__(
        self, db: Any, collections: Iterable[str], refs: Iterable[tuple[str, str, str, str]]
    ) -> None:
        self.db = db
        self.tables = sorted(collections)
        self.edges = [Edge(c, (cf,), p, (pf,), "document reference") for c, cf, p, pf in refs]
        self._cols: dict[str, list[str]] = {}
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def _rows(
        self, table: str, query: dict[str, Any] | None = None, limit: int = ROW_CAP
    ) -> list[dict[str, Any]]:
        return [_flat(d) for d in self.db[table].find(query or {}).limit(limit)]

    def fields(self, table: str) -> list[str]:
        if table not in self._cols:
            seen: dict[str, None] = {}
            for r in self._rows(table, limit=50):
                seen.update(dict.fromkeys(r))
            self._cols[table] = list(seen)
        return self._cols[table]

    def key_fields(self, table: str) -> list[str]:
        return ["_id"] if "_id" in self.fields(table) else []

    def table_rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self._cache:
            self._cache[table] = self._rows(table)
        return self._cache[table]

    def find(self, table: str, column: str, values: Sequence[Any]) -> list[dict[str, Any]]:
        vals = [v for v in values if v not in (None, "")]
        return self._rows(table, {column: {"$in": vals}}) if vals else []

    def join(
        self, edge: Edge, from_table: str, rows: list[dict[str, Any]], cap: int
    ) -> tuple[str, list[dict[str, Any]], str, int]:
        to_parent = edge.child == from_table
        src, dst = (
            (edge.child_fields[0], edge.parent_fields[0])
            if to_parent
            else (edge.parent_fields[0], edge.child_fields[0])
        )
        other = edge.parent if to_parent else edge.child
        values = sorted({str(r[src]) for r in rows if r.get(src) not in (None, "")})
        native = f"{other}.find({{{dst}: {{$in: <{len(values)} values from {from_table}.{src}>}}}})"
        found = self.find(other, dst, values) if values else []
        return other, found[:cap], native, len(found)

    def pk_dict(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        return {"_id": row.get("_id")}
