"""
inspect.py
----------
Validation report for Phase 3 Requirement 1, one source at a time:
tables and row counts, primary keys, foreign keys, SQLite's referential-integrity
check, and a multi-table join for a sample medicine.

    python -m integration.federation.inspect                  # all four sources
    python -m integration.federation.inspect --db db2         # only the one on this machine
    python -m integration.federation.inspect --item MED-RECALL-001 --json
"""

from __future__ import annotations
import argparse
import json
import os
import sys

from integration.uncertainty import paths
from integration.federation import medicine_views, nosql_store, schema_catalog

# Referential violations that are Phase 2 test data, not Phase 3 defects:
# purchase_events.vendor_id deliberately holds mistyped vendor ids ('vnd-10',
# 'VND 011') for the cleanser to repair. A cleansing run removes them.
KNOWN_PHASE2_NOISE = {"purchase_events(vendor_id) -> vendors(vendor_id)"}

# Medicines with records in each source: the cold-chain insulin is sold (DB1),
# shipped with a breach (DB2) and registered (DB3); the cough syrup was recalled (DB4).
DEMO_ITEMS = {"db1": "MED-ASALI-009", "db2": "MED-ASALI-009", "db3": "MED-ASALI-009", "db4": "MED-RECALL-001"}

NAMES = {"db1": "Retail POS (SQLite + JSON documents)", "db2": "Distributor ERP (SQLite)",
         "db3": "Manufacturer Registry (SQLite)", "db4": "Ministry Reports (SQLite behind REST)"}


def report(db_id: str, item: str) -> dict:
    path = paths.db_path(db_id)
    tables = schema_catalog.describe(path)
    out = {
        "database": db_id, "name": NAMES[db_id], "file": os.path.basename(path),
        "tables": {t.name: {"rows": t.rows, "primary_key": t.primary_key,
                            "foreign_keys": [fk.label() for fk in t.foreign_keys]} for t in tables.values()},
        "fk_connected_groups": schema_catalog.connected_tables(path),
        "integrity": schema_catalog.integrity_report(path),
    }
    view = {"db1": medicine_views.retail_view, "db2": medicine_views.distributor_view,
            "db3": medicine_views.registry_view, "db4": medicine_views.ministry_view}[db_id](item)
    out["join_demo"] = view
    if db_id == "db1":
        store = os.path.dirname(paths.nosql_file())
        out["documents"] = {"collections": {c: len(nosql_store.load(store, c))
                                            for c in list(nosql_store.COLLECTIONS) + [nosql_store.SCAN_COLLECTION]},
                            "references": nosql_store.check_references(store),
                            "document_view": medicine_views.document_view(item, store)}
    return out


def _print(r: dict) -> None:
    print("=" * 78)
    print(f"{r['database'].upper()}  {r['name']}   [{r['file']}]")
    print("=" * 78)
    for name, t in r["tables"].items():
        print(f"  {name:<30} {t['rows']:>6} rows   PK({', '.join(t['primary_key'])})")
    print("  Foreign keys:")
    for t in r["tables"].values():
        for fk in t["foreign_keys"]:
            print(f"    {fk}")
    groups = r["fk_connected_groups"]
    print(f"  FK-connected tables: {len(groups[0])} of {len(r['tables'])} in one group"
          + (f"; standalone: {', '.join(sum(groups[1:], []))}" if len(groups) > 1 else ""))
    ig = r["integrity"]
    print(f"  integrity_check: {ig['integrity_check']}   foreign keys checked: {len(ig['foreign_keys_checked'])}")
    if not ig["violations"]:
        print("  foreign_key_check: no violations")
    for fk, n in ig["violations"].items():
        tag = "  (Phase 2 deliberate noise)" if fk in KNOWN_PHASE2_NOISE else "  <-- PHASE 3 DEFECT"
        print(f"  foreign_key_check: {n} row(s) violate {fk}{tag}")
    for label, q in r["join_demo"].items():
        print(f"  JOIN [{label}]: {len(q['rows'])} row(s)")
        print(f"    {q['sql'][:300]}{'...' if len(q['sql']) > 300 else ''}")
        for row in q["rows"][:3]:
            print("    -> " + ", ".join(f"{k}={v}" for k, v in row.items() if v is not None)[:300])
    if "documents" in r:
        d = r["documents"]
        print("  Document collections (JSON, document references - not SQL foreign keys):")
        print("    " + ", ".join(f"{c} {n}" for c, n in d["collections"].items()))
        for ref in d["references"]:
            state = "ok" if not ref["dangling"] else f"{ref['dangling']} dangling e.g. {ref['dangling_examples'][:3]}"
            print(f"    {ref['collection']}.{ref['field']} -> {ref['target']} [{ref['kind']}]: {state}")
        dv = d["document_view"]
        print(f"    {dv['operation']}")
        print(f"    -> medicine={dv['medicine'] and dv['medicine']['brand_name']}, "
              f"inventory docs={len(dv['inventory'])}, scans={len(dv['scans'])}"
              + (f", first scan at {dv['scans'][0]['vendor']} via {dv['scans'][0]['terminal']}" if dv["scans"] else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 3 schema / integrity / join report")
    ap.add_argument("--db", choices=["db1", "db2", "db3", "db4"], action="append")
    ap.add_argument("--item", help="medicine to join on (default: one with records in that source)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    reports = [report(d, args.item or DEMO_ITEMS[d]) for d in (args.db or ["db1", "db2", "db3", "db4"])]
    if args.json:
        print(json.dumps(reports, indent=2, default=str))
    else:
        for r in reports:
            _print(r)
    defects = [fk for r in reports for fk in r["integrity"]["violations"] if fk not in KNOWN_PHASE2_NOISE]
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
