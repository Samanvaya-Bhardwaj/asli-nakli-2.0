"""
medicine_views.py
-----------------
Data-access functions that show one medicine spread across the tables of ONE
source, through that source's own primary-key / foreign-key joins.

Each function opens only the database it is about (read-only) and returns the
SQL it ran together with the rows, so the same call works unchanged on the
machine that hosts that database. Nothing here joins across databases: the
values that tie sources together (item code, batch number, distributor id,
manufacturer id, dispatch reference) are returned as business identifiers for
the Phase 3 mediator to use.
"""

from __future__ import annotations
import os
import sqlite3
from typing import Any, Dict, List, Optional

from integration.uncertainty import paths
from integration.federation import nosql_store


def _query(db_id: str, sql: str, params=(), db_path: Optional[str] = None) -> Dict[str, Any]:
    path = db_path or paths.db_path(db_id)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()
    return {"database": db_id, "sql": " ".join(sql.split()), "params": list(params), "rows": rows}


# -- DB1 retail POS: pharmacy x item master x inventory x goods receipt x sales x terminal

DB1_STOCK_SQL = """
SELECT rm.item_code, rm.brand_name, rm.generic_name, rm.schedule_class, rm.mrp_inr,
       v.vendor_id, v.vendor_name, v.location_county AS city,
       inv.quantity_on_hand, inv.shelf_location,
       sr.receipt_id, sr.received_on, sr.quantity_received,
       sr.supplier_distributor_id, sr.supplier_dispatch_ref
FROM retail_medicines rm
JOIN inventory inv     ON inv.item_code = rm.item_code
JOIN vendors v         ON v.vendor_id = inv.vendor_id
LEFT JOIN stock_receipts sr ON sr.receipt_id = inv.last_receipt_id
WHERE rm.item_code = ?
ORDER BY v.vendor_id
"""

DB1_SALES_SQL = """
SELECT pe.event_id, pe.scan_timestamp, pe.quantity_bought, pe.price_paid, pe.scan_method,
       v.vendor_id, v.vendor_name, t.device_id, t.terminal_model, t.scanner_type,
       rm.brand_name AS item_master_brand
FROM purchase_events pe
JOIN vendors v              ON v.vendor_id = pe.vendor_id
JOIN pos_terminals t        ON t.device_id = pe.device_id
LEFT JOIN retail_medicines rm ON rm.item_code = pe.scan_code
WHERE pe.scan_code = ?
ORDER BY pe.scan_timestamp
"""


def retail_view(item_code: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    return {"stock": _query("db1", DB1_STOCK_SQL, (item_code,), db_path),
            "sales": _query("db1", DB1_SALES_SQL, (item_code,), db_path)}


# -- DB2 distributor ERP: shipment x distributor x warehouse x logger x readings

DB2_SHIPMENT_SQL = """
SELECT b.batch_id, b.batch_serial, b.dispatch_date, b.actual_arrival_date, b.destination_vendor_id,
       b.cold_chain_maintained, d.distributor_id, d.company_name AS distributor, d.is_authorized,
       w.warehouse_id, w.warehouse_name, w.city AS warehouse_city, w.verification_status AS warehouse_status,
       l.logger_id, l.profile, l.setpoint_min_c, l.setpoint_max_c,
       COUNT(t.reading_id) AS readings, COALESCE(SUM(t.excursion), 0) AS excursion_readings,
       MIN(t.temperature_c) AS min_temp_c, MAX(t.temperature_c) AS max_temp_c
FROM distribution_batches b
JOIN distributors d          ON d.distributor_id = b.distributor_id
LEFT JOIN warehouses w       ON w.distributor_id = b.distributor_id AND w.warehouse_name = b.source_warehouse
LEFT JOIN cold_chain_loggers l ON l.batch_id = b.batch_id
LEFT JOIN temperature_logs t ON t.logger_id = l.logger_id
WHERE b.batch_serial = ?
GROUP BY b.batch_id
ORDER BY b.dispatch_date
"""


def distributor_view(item_code: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    return {"shipments": _query("db2", DB2_SHIPMENT_SQL, (item_code,), db_path)}


# -- DB3 registry: product x molecule x manufacturer x site x production run x QC certificate

DB3_REGISTRY_SQL = """
SELECT p.product_uid, p.product_name, p.batch_number, p.manufacture_date, p.expiry_date, p.is_recalled,
       mo.molecule_id, mo.generic_name, mo.atc_code, mo.schedule_class, mo.cold_chain_required,
       m.manufacturer_id, m.company_name AS manufacturer,
       s.site_id, s.site_name, s.state AS site_state, s.gmp_status,
       pr.production_id, pr.started_on, pr.completed_on, pr.batch_size_units, pr.yield_percent,
       c.cert_id, c.qc_passed, c.release_date, c.qc_officer
FROM products p
JOIN manufacturers m             ON m.manufacturer_id = p.manufacturer_id
LEFT JOIN molecules mo           ON mo.generic_name = p.generic_name
LEFT JOIN production_records pr  ON pr.product_uid = p.product_uid
LEFT JOIN manufacturing_sites s  ON s.site_id = pr.site_id
LEFT JOIN batch_release_certs c  ON c.product_uid = p.product_uid
WHERE p.product_uid = ?
"""


def registry_view(item_code: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    return {"registration": _query("db3", DB3_REGISTRY_SQL, (item_code,), db_path)}


# -- DB4 ministry: recall x authority (x parent) x officer x complaint x lab report x alert

DB4_RECALL_SQL = """
SELECT r.recall_id, r.recall_class, r.issued_on, r.batch_ref, r.manufacturer_ref, r.reason,
       a.authority_name AS issuing_authority, pa.authority_name AS parent_authority,
       o.officer_id, o.full_name AS officer,
       c.complaint_id, c.complaint_category, c.status AS complaint_status,
       l.lab_report_id, l.result AS lab_result, l.findings_summary,
       al.alert_id, al.channel AS alert_channel
FROM recall_notices r
JOIN regulatory_authorities a       ON a.authority_id = r.authority_id
LEFT JOIN regulatory_authorities pa ON pa.authority_id = a.parent_authority_id
LEFT JOIN ministry_officers o       ON o.officer_id = r.issuing_officer_id
LEFT JOIN complaints c              ON c.complaint_id = r.complaint_id
LEFT JOIN lab_reports l             ON l.lab_report_id = r.lab_report_id
LEFT JOIN public_alerts al          ON al.alert_id = r.alert_id
WHERE r.item_ref = ?
"""

DB4_COMPLAINT_SQL = """
SELECT c.complaint_id, c.complaint_date, c.complaint_category, c.severity_level, c.status,
       o.officer_id, o.full_name AS officer, a.authority_id, a.authority_name, a.authority_type,
       b.blacklist_id, b.severity AS blacklist_severity
FROM complaints c
LEFT JOIN ministry_officers o       ON o.officer_id = c.assigned_officer_id
LEFT JOIN regulatory_authorities a  ON a.authority_name = o.department
LEFT JOIN ministry_blacklist b      ON b.complaint_id = c.complaint_id
WHERE c.complaint_item_ref = ?
ORDER BY c.complaint_date
"""


def ministry_view(item_ref: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    return {"recalls": _query("db4", DB4_RECALL_SQL, (item_ref,), db_path),
            "complaints": _query("db4", DB4_COMPLAINT_SQL, (item_ref,), db_path)}


# -- DB1 document store: the same medicine through document references

def document_view(item_code: str, store_dir: Optional[str] = None) -> Dict[str, Any]:
    """Follows the declared document references from the scans of one code."""
    store = store_dir or os.path.dirname(paths.nosql_file())
    by_id = {c: {d["_id"]: d for d in nosql_store.load(store, c)} for c in nosql_store.COLLECTIONS}
    scans = [d for d in nosql_store.load(store, nosql_store.SCAN_COLLECTION) if d.get("scan_code") == item_code]
    medicine = by_id["retail_medicines"].get(item_code)
    stock = [d for d in by_id["inventory"].values() if d.get("item_ref") == item_code]
    out = []
    for s in scans:
        vendor = by_id["vendors"].get(nosql_store.get_path(s, "dispensary.vendor_id"))
        terminal = by_id["pos_terminals"].get(nosql_store.get_path(s, "pos_terminal.device_id"))
        out.append({"scan": s["_id"], "when": nosql_store.get_path(s, "transaction.timestamp_iso"),
                    "vendor": vendor and vendor["name"], "terminal": terminal and terminal["model"]})
    return {"store": store, "operation": (f"find(retail_pos_scans, {{scan_code: '{item_code}'}}) -> "
                                          "lookup vendors by dispensary.vendor_id, pos_terminals by "
                                          "pos_terminal.device_id, retail_medicines by _id, inventory by item_ref"),
            "medicine": medicine, "inventory": stock, "scans": out}


def views_for(item_code: str) -> Dict[str, Any]:
    return {"db1": retail_view(item_code), "db1_documents": document_view(item_code),
            "db2": distributor_view(item_code), "db3": registry_view(item_code), "db4": ministry_view(item_code)}
