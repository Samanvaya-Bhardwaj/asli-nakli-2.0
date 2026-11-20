#!/usr/bin/env python3
"""
prepare_node_data.py
--------------------
Gives each database service a data directory holding ONLY its own database,
which is what a separate machine has. Run it where the full project data is
(after scripts/rebuild_data.py or scripts/migrate_phase3.py), then copy each
folder to the machine that will host that database.

    python scripts/prepare_node_data.py                       # all four, into deploy/nodes/
    python scripts/prepare_node_data.py --db db3 --db db4     # only Machine 2's
    python scripts/prepare_node_data.py --out D:/asali-nodes

Layout produced (what ASALI_DB_DIR / ASALI_NOSQL_FILE point at):
    <out>/db1/databases/db1_purchase_registry.sqlite
    <out>/db1/nosql_store/db1_*.json            (scans + Phase 3 collections + manifest)
    <out>/db2/databases/db2_distributor_ledger.sqlite
    <out>/db3/databases/db3_manufacturer_registry.sqlite
    <out>/db4/databases/db4_ministry_reports.sqlite

SQLite files are copied with the online backup API, so a copy taken while a
Phase 1/2 node is running is still consistent.
"""

from __future__ import annotations
import argparse
import glob
import os
import shutil
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

FILES = {"db1": "db1_purchase_registry.sqlite", "db2": "db2_distributor_ledger.sqlite",
         "db3": "db3_manufacturer_registry.sqlite", "db4": "db4_ministry_reports.sqlite"}


def prepare(db_id: str, out_root: str, src_db_dir: str, src_nosql_dir: str) -> list:
    node = os.path.join(out_root, db_id)
    if os.path.isdir(node):
        shutil.rmtree(node)
    os.makedirs(os.path.join(node, "databases"))
    written = []
    src = os.path.join(src_db_dir, FILES[db_id])
    if not os.path.exists(src):
        raise SystemExit(f"missing source database: {src}")
    dst = os.path.join(node, "databases", FILES[db_id])
    a, b = sqlite3.connect(f"file:{src}?mode=ro", uri=True), sqlite3.connect(dst)
    try:
        a.backup(b)
    finally:
        a.close()
        b.close()
    written.append(dst)
    if db_id == "db1":
        os.makedirs(os.path.join(node, "nosql_store"))
        for f in sorted(glob.glob(os.path.join(src_nosql_dir, "db1_*.json"))):
            shutil.copy2(f, os.path.join(node, "nosql_store", os.path.basename(f)))
            written.append(os.path.join(node, "nosql_store", os.path.basename(f)))
    return written


def main():
    ap = argparse.ArgumentParser(description="Per-database data directories for separate machines")
    ap.add_argument("--db", action="append", choices=list(FILES))
    ap.add_argument("--out", default=os.path.join(BASE, "deploy", "nodes"))
    ap.add_argument("--source-db-dir", default=os.path.join(BASE, "databases"))
    ap.add_argument("--source-nosql-dir", default=os.path.join(BASE, "data", "nosql_store"))
    args = ap.parse_args()
    for d in args.db or list(FILES):
        files = prepare(d, args.out, args.source_db_dir, args.source_nosql_dir)
        print(f"  {d}: {len(files)} file(s) -> {os.path.join(args.out, d)}")


if __name__ == "__main__":
    main()
