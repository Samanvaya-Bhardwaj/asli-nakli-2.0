#!/usr/bin/env python3
"""
migrate_phase3.py
-----------------
Upgrades existing Phase 1/2 databases to the Phase 3 schema in place, keeping
every row (including Phase 2 cleansing results), then fills the Phase 3 tables
and refreshes DB1's document collections.

    python scripts/migrate_phase3.py                 # all four databases
    python scripts/migrate_phase3.py --db db2        # only the database on this machine
    python scripts/migrate_phase3.py --schema-only   # tables and keys, no seeding

Running it twice changes nothing the second time (the seeding step regenerates
the Phase 3 tables from the same rows, so it produces identical contents).
Seeding a single database reads the DB3 registry file to derive rows, the same
way the Phase 2 generator does; run it where all four files are present (or on
a copy), then ship each file to the machine that hosts it.
"""

from __future__ import annotations
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from integration.federation.migrate import migrate_all  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Migrate databases to the Phase 3 schema")
    ap.add_argument("--db", choices=["db1", "db2", "db3", "db4"], action="append")
    ap.add_argument("--schema-only", action="store_true")
    args = ap.parse_args()
    dbs = args.db or ["db1", "db2", "db3", "db4"]

    print("[1/3] Schema")
    for r in migrate_all(dbs):
        print(f"  {r['database']}: created {r['created'] or '-'}; "
              f"rebuilt with new foreign keys {dict(r['rebuilt']) or '-'} (rows kept); "
              f"unchanged {len(r['unchanged'])}; triggers {len(r['triggers'])}"
              + (f"; not in schema, left alone {r['left_alone']}" if r["left_alone"] else ""))
    if args.schema_only:
        return
    print("[2/3] Phase 3 rows")
    from data import seed_phase3
    fns = {"db3": seed_phase3.seed_db3, "db2": seed_phase3.seed_db2,
           "db1": seed_phase3.seed_db1, "db4": seed_phase3.seed_db4}
    for d in ("db3", "db2", "db1", "db4"):
        if d in dbs:
            print(f"  {d}: " + ", ".join(f"{k} {v}" for k, v in fns[d]().items()))
    print("[3/3] DB1 document collections")
    if "db1" in dbs:
        from data.seed_nosql_db1 import sync_collection
        from integration.uncertainty import paths
        print(f"  {sync_collection(paths.db_path('db1'), paths.nosql_file())} scan documents, plus Phase 3 collections")
    else:
        print("  skipped (DB1 not selected)")


if __name__ == "__main__":
    main()
