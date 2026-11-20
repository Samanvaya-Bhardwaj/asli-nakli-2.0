"""
nosql_store.py
--------------
DB1's document-store side for the Phase 3 entities.

DB1 is two representations of one retail system (established in Phase 1/2):
SQLite tables are authoritative for writes, and a JSON document collection is
the NoSQL view that the mediator queries. Phase 3 keeps that arrangement:

  data/nosql_store/db1_retail_pos.json      checkout scans (unchanged shape)
  data/nosql_store/db1_vendors.json         pharmacies
  data/nosql_store/db1_pos_terminals.json   tills and cameras
  data/nosql_store/db1_retail_medicines.json  item master
  data/nosql_store/db1_stock_receipts.json  goods received notes
  data/nosql_store/db1_inventory.json       stock on hand
  data/nosql_store/db1_collections.json     manifest: collections and references

A document store has no foreign keys. Links between collections are *document
references*: a field holding another document's _id, declared in the manifest
and checked by check_references() below. They are reported as references, never
as SQL foreign keys. The collections are rebuilt from SQLite on every DB1 write,
by data/seed_nosql_db1.sync_collection().
"""

from __future__ import annotations
import json
import os
import sqlite3
from typing import Any, Dict, List

SCAN_COLLECTION = "retail_pos_scans"

# name -> (file, source SQLite table)
COLLECTIONS = {
    "vendors":          ("db1_vendors.json", "vendors"),
    "pos_terminals":    ("db1_pos_terminals.json", "pos_terminals"),
    "retail_medicines": ("db1_retail_medicines.json", "retail_medicines"),
    "stock_receipts":   ("db1_stock_receipts.json", "stock_receipts"),
    "inventory":        ("db1_inventory.json", "inventory"),
}
SCAN_FILE = "db1_retail_pos.json"
MANIFEST_FILE = "db1_collections.json"

# (collection, field path, target collection, kind)
REFERENCES = [
    ("pos_terminals",    "vendor_ref",                "vendors",          "document_reference"),
    ("stock_receipts",   "vendor_ref",                "vendors",          "document_reference"),
    ("stock_receipts",   "item_ref",                  "retail_medicines", "document_reference"),
    ("inventory",        "vendor_ref",                "vendors",          "document_reference"),
    ("inventory",        "item_ref",                  "retail_medicines", "document_reference"),
    ("inventory",        "last_receipt_ref",          "stock_receipts",   "document_reference"),
    (SCAN_COLLECTION,    "dispensary.vendor_id",      "vendors",          "document_reference"),
    (SCAN_COLLECTION,    "pos_terminal.device_id",    "pos_terminals",    "document_reference"),
    # a scanned code may be damaged or counterfeit, so this one is a lookup, not an integrity rule
    (SCAN_COLLECTION,    "scan_code",                 "retail_medicines", "business_key_lookup"),
]


def _rows(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]
    except sqlite3.OperationalError:     # database not migrated to Phase 3 yet
        return []


def build_collections(db_path: str) -> Dict[str, List[Dict[str, Any]]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        vendors = [{
            "_id": v["vendor_id"], "name": v["vendor_name"], "type": v["vendor_type"],
            "license": {"number": v["license_no"], "expiry": v["license_expiry"], "is_active": bool(v["active"])},
            "location": {"city": v["location_county"], "street": v["location_street"]},
            "contact": {"phone": v["phone"], "email": v["email"]},
            "registered_on": v["registered_on"],
        } for v in _rows(conn, "vendors")]
        terminals = [{
            "_id": t["device_id"], "vendor_ref": t["vendor_id"], "model": t["terminal_model"],
            "scanner_type": t["scanner_type"], "firmware_version": t["firmware_version"],
            "installed_on": t["installed_on"], "status": t["registration_status"],
        } for t in _rows(conn, "pos_terminals")]
        medicines = [{
            "_id": m["item_code"], "brand_name": m["brand_name"], "generic_name": m["generic_name"],
            "strength": m["strength"], "pack_size": m["pack_size"],
            "batch": {"number": m["batch_number"], "expiry_date": m["expiry_date"]},
            "pricing": {"mrp": m["mrp_inr"], "currency": "INR"},
            "regulatory": {"schedule_class": m["schedule_class"], "manufacturer_id": m["manufacturer_id"]},
            "added_on": m["added_on"],
        } for m in _rows(conn, "retail_medicines")]
        receipts = [{
            "_id": r["receipt_id"], "vendor_ref": r["vendor_id"], "item_ref": r["item_code"],
            "supplier": {"distributor_id": r["supplier_distributor_id"], "dispatch_ref": r["supplier_dispatch_ref"],
                         "invoice_no": r["invoice_no"]},
            "received_on": r["received_on"], "quantity": r["quantity_received"],
        } for r in _rows(conn, "stock_receipts")]
        inventory = [{
            "_id": i["inventory_id"], "vendor_ref": i["vendor_id"], "item_ref": i["item_code"],
            "stock": {"on_hand": i["quantity_on_hand"], "reorder_level": i["reorder_level"],
                      "shelf": i["shelf_location"], "last_stock_take": i["last_stock_take"]},
            "last_receipt_ref": i["last_receipt_id"],
        } for i in _rows(conn, "inventory")]
    finally:
        conn.close()
    return {"vendors": vendors, "pos_terminals": terminals, "retail_medicines": medicines,
            "stock_receipts": receipts, "inventory": inventory}


def manifest() -> Dict[str, Any]:
    return {
        "store": "DB1 retail POS document store (JSON collections)",
        "paradigm": "document",
        "note": ("Links between collections are document references (a field holding another document's _id). "
                 "They are not SQL foreign keys; check_references() verifies them. "
                 "Collections are mirrored from DB1's authoritative SQLite tables on every write."),
        "collections": dict({name: {"file": f, "primary_key": "_id", "mirrors_sqlite_table": t}
                             for name, (f, t) in COLLECTIONS.items()},
                            **{SCAN_COLLECTION: {"file": SCAN_FILE, "primary_key": "_id",
                                                 "mirrors_sqlite_table": "purchase_events (joined with vendors)"}}),
        "references": [{"collection": c, "field": f, "target": t, "kind": k} for c, f, t, k in REFERENCES],
    }


def write_collections(db_path: str, store_dir: str) -> Dict[str, int]:
    docs = build_collections(db_path)
    os.makedirs(store_dir, exist_ok=True)
    for name, (fname, _t) in COLLECTIONS.items():
        with open(os.path.join(store_dir, fname), "w", encoding="utf-8") as f:
            json.dump(docs[name], f, indent=1)
    with open(os.path.join(store_dir, MANIFEST_FILE), "w", encoding="utf-8") as f:
        json.dump(manifest(), f, indent=2)
    return {name: len(v) for name, v in docs.items()}


def load(store_dir: str, collection: str) -> List[Dict[str, Any]]:
    fname = SCAN_FILE if collection == SCAN_COLLECTION else COLLECTIONS[collection][0]
    path = os.path.join(store_dir, fname)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_path(doc: Dict[str, Any], dotted: str):
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def check_references(store_dir: str) -> List[Dict[str, Any]]:
    """For every declared reference: how many documents point at a document that does not exist."""
    ids = {c: {d.get("_id") for d in load(store_dir, c)} for c in list(COLLECTIONS) + [SCAN_COLLECTION]}
    out = []
    for coll, field, target, kind in REFERENCES:
        values = [get_path(d, field) for d in load(store_dir, coll)]
        present = [v for v in values if v not in (None, "")]
        dangling = [v for v in present if v not in ids[target]]
        out.append({"collection": coll, "field": field, "target": target, "kind": kind,
                    "documents": len(values), "with_value": len(present), "dangling": len(dangling),
                    "dangling_examples": sorted(set(map(str, dangling)))[:6]})
    return out
