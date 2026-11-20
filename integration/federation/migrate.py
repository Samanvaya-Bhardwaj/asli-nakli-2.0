"""
migrate.py
----------
Brings an existing database up to the schema in schema/schema_dbN.sql, in place,
without losing a row. Safe to run any number of times.

create_databases.py builds a database from scratch, which deletes whatever was
in it (including Phase 2 cleansing results). This module never deletes data:

  * a table in the schema file but not in the database      -> created
  * a table whose columns match but whose foreign keys do
    not (Phase 3 added a key to an existing column)         -> rebuilt: new table,
                                                               rows copied, old one
                                                               dropped, new one renamed
                                                               (SQLite cannot add a
                                                               constraint any other way)
  * a table whose columns differ from the schema file       -> refused, with the
                                                               difference reported
  * tables the schema file does not mention (item_lifecycle,
    created on demand by lifecycle_state.py)                -> left alone

Indexes and triggers are then (re)created from the schema file. Each rebuild runs
in its own transaction and checks that the copied rows are identical.
"""

from __future__ import annotations
import os
import re
import sqlite3
from typing import Dict, List, Set, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_DIR = os.path.join(BASE_DIR, "schema")
SCHEMA_FILES = {
    "db1": "schema_db1.sql",
    "db2": "schema_db2.sql",
    "db3": "schema_db3.sql",
    "db4": "schema_db4.sql",
}


class MigrationError(RuntimeError):
    pass


def schema_sql(db_id: str, schema_dir: str = SCHEMA_DIR) -> str:
    with open(os.path.join(schema_dir, SCHEMA_FILES[db_id]), "r", encoding="utf-8") as f:
        return f.read()


def _columns(conn, table) -> List[Tuple]:
    return [(r[1], (r[2] or "").upper(), r[3], r[4], r[5]) for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _fks(conn, table) -> Set[Tuple]:
    groups: Dict[int, list] = {}
    for fk_id, seq, ref_table, frm, to, *_ in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
        groups.setdefault(fk_id, []).append((seq, frm, to, ref_table))
    out = set()
    for rows in groups.values():
        rows.sort()
        out.add((rows[0][3], tuple(r[1] for r in rows), tuple(r[2] for r in rows)))
    return out


def _objects(conn, kind: str) -> Dict[str, str]:
    return {name: sql for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%' ORDER BY rowid", (kind,))}


def _rows(conn, table, cols) -> List[tuple]:
    col_sql = ", ".join(f'"{c}"' for c in cols)
    return sorted(conn.execute(f'SELECT {col_sql} FROM "{table}"').fetchall(), key=repr)


def _rebuild(conn, table: str, create_sql: str) -> int:
    """SQLite's documented procedure for changing a table's constraints."""
    tmp = f"__phase3_new_{table}"
    new_sql, n = re.subn(r'^\s*CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?("?[\w]+"?)',
                         f'CREATE TABLE "{tmp}"', create_sql, count=1, flags=re.I)
    if n != 1:
        raise MigrationError(f"cannot parse CREATE TABLE for {table}")
    cols = [c[0] for c in _columns(conn, table)]
    before = _rows(conn, table, cols)
    col_sql = ", ".join(f'"{c}"' for c in cols)
    conn.execute("BEGIN")
    try:
        conn.execute(f'DROP TABLE IF EXISTS "{tmp}"')
        conn.execute(new_sql)
        conn.execute(f'INSERT INTO "{tmp}" ({col_sql}) SELECT {col_sql} FROM "{table}"')
        conn.execute(f'DROP TABLE "{table}"')
        conn.execute(f'ALTER TABLE "{tmp}" RENAME TO "{table}"')
        after = _rows(conn, table, cols)
        if after != before:
            raise MigrationError(f"{table}: rows changed during rebuild")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(after)


def reconcile(db_path: str, sql: str) -> Dict[str, object]:
    """Migrate one database file to the schema text `sql`. Returns what was done."""
    if not os.path.exists(db_path):
        raise MigrationError(f"database not found: {db_path}")
    target = sqlite3.connect(":memory:")
    target.executescript(sql)
    report = {"database": os.path.basename(db_path), "created": [], "rebuilt": {}, "unchanged": [],
              "left_alone": [], "triggers": [], "indexes": 0}

    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")        # constraints are added, not enforced, here
        conn.execute("PRAGMA legacy_alter_table = ON")   # rename without rewriting other objects
        # Drop the schema's own triggers first; they are recreated below, and a
        # trigger naming a table mid-rebuild would make the rename fail.
        for name in _objects(target, "trigger"):
            conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')

        existing = set(_objects(conn, "table"))
        target_tables = _objects(target, "table")
        for table, create_sql in target_tables.items():
            if table not in existing:
                conn.execute(create_sql)
                report["created"].append(table)
                continue
            have, want = _columns(conn, table), _columns(target, table)
            if have != want:
                raise MigrationError(
                    f"{report['database']}.{table}: columns differ from the schema file; refusing to migrate.\n"
                    f"  database: {[c[0] for c in have]}\n  schema:   {[c[0] for c in want]}")
            if _fks(conn, table) != _fks(target, table):
                report["rebuilt"][table] = _rebuild(conn, table, create_sql)
            else:
                report["unchanged"].append(table)
        report["left_alone"] = sorted(existing - set(target_tables))

        conn.executescript(sql)   # indexes and triggers (every CREATE is IF NOT EXISTS)
        report["triggers"] = sorted(_objects(conn, "trigger"))
        report["indexes"] = len(_objects(conn, "index"))
    finally:
        conn.close()
        target.close()
    return report


def migrate_all(db_ids=("db1", "db2", "db3", "db4"), schema_dir: str = SCHEMA_DIR) -> List[Dict[str, object]]:
    from integration.uncertainty import paths
    return [reconcile(paths.db_path(d), schema_sql(d, schema_dir)) for d in db_ids]
