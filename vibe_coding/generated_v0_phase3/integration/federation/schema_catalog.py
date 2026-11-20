"""
schema_catalog.py
-----------------
Reads the relational structure of ONE SQLite source from the file itself:
tables, row counts, primary keys, foreign keys (including composite ones) and
the result of SQLite's own referential-integrity check.

Nothing is hard-coded: the catalogue is whatever PRAGMA table_info and
PRAGMA foreign_key_list report, so it stays correct after any schema change.
Phase 3 local context discovery walks the graph this module returns.
"""

from __future__ import annotations
import sqlite3
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple


@dataclass
class ForeignKey:
    table: str                 # child table
    columns: Tuple[str, ...]   # child columns
    ref_table: str             # parent table
    ref_columns: Tuple[str, ...]

    def label(self) -> str:
        return f"{self.table}({', '.join(self.columns)}) -> {self.ref_table}({', '.join(self.ref_columns)})"


@dataclass
class TableInfo:
    name: str
    rows: int
    primary_key: List[str]
    columns: List[str]
    unique_keys: List[List[str]] = field(default_factory=list)
    foreign_keys: List[ForeignKey] = field(default_factory=list)


def _ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def user_tables(conn: sqlite3.Connection) -> List[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]


def foreign_keys(conn: sqlite3.Connection, table: str) -> List[ForeignKey]:
    groups: Dict[int, list] = {}
    for fk_id, seq, ref_table, frm, to, *_ in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
        groups.setdefault(fk_id, []).append((seq, frm, to, ref_table))
    out = []
    for rows in groups.values():
        rows.sort()
        out.append(ForeignKey(table, tuple(r[1] for r in rows), rows[0][3], tuple(r[2] for r in rows)))
    return sorted(out, key=lambda f: (f.ref_table, f.columns))


def unique_keys(conn: sqlite3.Connection, table: str) -> List[List[str]]:
    keys = []
    for _seq, name, unique, origin, _partial in conn.execute(f'PRAGMA index_list("{table}")'):
        if unique and origin in ("u", "pk"):
            keys.append([r[2] for r in conn.execute(f'PRAGMA index_info("{name}")')])
    return keys


def describe(db_path: str) -> Dict[str, TableInfo]:
    conn = _ro(db_path)
    try:
        out = {}
        for t in user_tables(conn):
            info = list(conn.execute(f'PRAGMA table_info("{t}")'))
            pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5]]
            out[t] = TableInfo(
                name=t,
                rows=conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0],
                primary_key=pk,
                columns=[r[1] for r in info],
                unique_keys=unique_keys(conn, t),
                foreign_keys=foreign_keys(conn, t),
            )
        return out
    finally:
        conn.close()


def fk_edges(db_path: str) -> List[ForeignKey]:
    return [fk for t in describe(db_path).values() for fk in t.foreign_keys]


def connected_tables(db_path: str) -> List[List[str]]:
    """Groups of tables linked to each other by foreign keys (undirected)."""
    tables = describe(db_path)
    parent = {t: t for t in tables}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for t in tables.values():
        for fk in t.foreign_keys:
            if fk.ref_table in parent:
                parent[find(fk.table)] = find(fk.ref_table)
    groups: Dict[str, List[str]] = {}
    for t in tables:
        groups.setdefault(find(t), []).append(t)
    return sorted(groups.values(), key=len, reverse=True)


def integrity_report(db_path: str) -> Dict[str, object]:
    """
    SQLite's own checks, run read-only:
      integrity_check     - page / index structure
      foreign_key_check   - every child row whose parent row does not exist
    Violations are grouped by foreign key so a reader sees *which* relationship
    is broken, not just how many rows.
    """
    conn = _ro(db_path)
    try:
        structure = conn.execute("PRAGMA integrity_check").fetchone()[0]
        # foreign_key_check rows are (table, rowid, parent, fkid), where fkid is the
        # id column of PRAGMA foreign_key_list, so key the labels on that id.
        fks: Dict[str, Dict[int, ForeignKey]] = {}
        for t in user_tables(conn):
            groups: Dict[int, list] = {}
            for fk_id, seq, ref_table, frm, to, *_ in conn.execute(f'PRAGMA foreign_key_list("{t}")'):
                groups.setdefault(fk_id, []).append((seq, frm, to, ref_table))
            fks[t] = {fid: ForeignKey(t, tuple(r[1] for r in sorted(rows)), rows[0][3],
                                      tuple(r[2] for r in sorted(rows)))
                      for fid, rows in groups.items()}
        by_fk: Counter = Counter()
        for table, _rowid, parent, fkid in conn.execute("PRAGMA foreign_key_check"):
            fk = fks.get(table, {}).get(fkid)
            by_fk[fk.label() if fk else f"{table} -> {parent}"] += 1
        checked = [fk.label() for t in fks.values() for fk in t.values()]
        return {
            "integrity_check": structure,
            "foreign_keys_checked": checked,
            "violations": dict(by_fk),
            "violation_rows": sum(by_fk.values()),
        }
    finally:
        conn.close()


def as_dict(db_path: str) -> Dict[str, object]:
    return {name: {**asdict(t), "foreign_keys": [fk.label() for fk in t.foreign_keys]}
            for name, t in describe(db_path).items()}
