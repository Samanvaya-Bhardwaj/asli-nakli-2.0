"""
Phase 3, Requirement 1: related tables, keys and referential integrity.

Builds a throwaway copy of the four silos exactly as Phase 2 left them (the
schema frozen in vibe_coding/phase2_baseline/schema), migrates it in place to
the Phase 3 schema, seeds the Phase 3 tables, and checks:

  * migration keeps every Phase 1/2 row and is idempotent
  * the migrated schema is identical to a fresh build from schema/
  * each source has at least five tables tied together by foreign keys
  * SQLite's foreign_key_check finds nothing but the Phase 2 deliberate noise
  * the per-source joins return connected rows for known medicines
  * derived data agrees with what it was derived from
  * the integrity triggers keep legacy writes from leaving dangling keys
  * DB1's document references resolve

    python -m unittest tests.test_phase3_schema -v
"""

from __future__ import annotations
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TMP = tempfile.mkdtemp(prefix="asali_p3_")
os.environ["ASALI_DB_DIR"] = os.path.join(TMP, "databases")
os.environ["ASALI_NOSQL_FILE"] = os.path.join(TMP, "nosql", "db1_retail_pos.json")
os.environ["ASALI_GENERATED_DIR"] = os.path.join(TMP, "generated")

from integration.uncertainty import paths                              # noqa: E402
from integration.federation import medicine_views, migrate, nosql_store, schema_catalog  # noqa: E402

PHASE2_SCHEMA = os.path.join(BASE, "vibe_coding", "phase2_baseline", "schema")
DBS = ("db1", "db2", "db3", "db4")
NEW_TABLES = {
    "db1": ["pos_terminals", "retail_medicines", "stock_receipts", "inventory"],
    "db2": ["warehouses", "cold_chain_loggers", "temperature_logs"],
    "db3": ["molecules", "manufacturing_sites", "production_records", "batch_release_certs"],
    "db4": ["regulatory_authorities", "recall_notices"],
}
PHASE2_NOISE = {"purchase_events(vendor_id) -> vendors(vendor_id)"}
SNAPSHOT = {}
FIRST_MIGRATION = []


def sql(db, query, params=()):
    conn = sqlite3.connect(paths.db_path(db))
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.fetchall()
    finally:
        conn.close()


def table_rows(db, table):
    conn = sqlite3.connect(paths.db_path(db))
    try:
        return sorted(conn.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr)
    finally:
        conn.close()


def setUpModule():
    os.makedirs(paths.db_dir(), exist_ok=True)
    os.makedirs(paths.generated_dir(), exist_ok=True)
    import create_databases
    from data import generate_uncertain_data, seed_db1, seed_db2, seed_db3, seed_db4, seed_phase3
    from data.seed_nosql_db1 import sync_collection
    create_databases.SCHEMA_DIR = PHASE2_SCHEMA          # the databases as Phase 2 built them
    create_databases.main()
    for seed in (seed_db3, seed_db2, seed_db1, seed_db4):
        seed.seed()
    generate_uncertain_data.main()
    for d in DBS:
        conn = sqlite3.connect(paths.db_path(d))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                             "AND name NOT LIKE 'sqlite_%'")]
        conn.close()
        SNAPSHOT[d] = {t: table_rows(d, t) for t in tables}
    FIRST_MIGRATION.extend(migrate.migrate_all())
    seed_phase3.main()
    sync_collection(paths.db_path("db1"), paths.nosql_file())


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class Migration(unittest.TestCase):

    def test_first_migration_created_and_rebuilt_the_expected_tables(self):
        by_db = {r["database"]: r for r in FIRST_MIGRATION}
        self.assertEqual(set(by_db["db1_purchase_registry.sqlite"]["created"]),
                         {"pos_terminals", "retail_medicines", "stock_receipts", "inventory"})
        self.assertIn("purchase_events", by_db["db1_purchase_registry.sqlite"]["rebuilt"])
        self.assertIn("distribution_batches", by_db["db2_distributor_ledger.sqlite"]["rebuilt"])
        self.assertIn("products", by_db["db3_manufacturer_registry.sqlite"]["rebuilt"])
        self.assertEqual(set(by_db["db4_ministry_reports.sqlite"]["rebuilt"]), {"ministry_officers", "public_alerts"})

    def test_every_phase2_row_survived(self):
        for d, tables in SNAPSHOT.items():
            for t, rows in tables.items():
                if t in NEW_TABLES[d]:        # Phase 2 had these empty (batch_release_certs) or absent
                    continue
                with self.subTest(db=d, table=t):
                    self.assertEqual(table_rows(d, t), rows)

    def test_migration_is_idempotent(self):
        for r in migrate.migrate_all():
            self.assertEqual(r["created"], [], r["database"])
            self.assertEqual(r["rebuilt"], {}, r["database"])

    def test_migrated_schema_matches_a_fresh_build(self):
        for d in DBS:
            fresh = sqlite3.connect(":memory:")
            fresh.executescript(migrate.schema_sql(d))
            live = sqlite3.connect(paths.db_path(d))
            for (t,) in fresh.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                with self.subTest(db=d, table=t):
                    self.assertEqual(migrate._columns(live, t), migrate._columns(fresh, t))
                    self.assertEqual(migrate._fks(live, t), migrate._fks(fresh, t))
            live.close()
            fresh.close()


class Structure(unittest.TestCase):

    def test_each_source_has_at_least_five_connected_tables(self):
        for d in DBS:
            groups = schema_catalog.connected_tables(paths.db_path(d))
            with self.subTest(db=d):
                self.assertGreaterEqual(len(groups[0]), 5, groups)

    def test_new_tables_are_populated(self):
        for d, tables in NEW_TABLES.items():
            for t in tables:
                with self.subTest(db=d, table=t):
                    self.assertGreater(sql(d, f"SELECT COUNT(*) FROM {t}")[0][0], 0)

    def test_referential_integrity(self):
        for d in DBS:
            rep = schema_catalog.integrity_report(paths.db_path(d))
            with self.subTest(db=d):
                self.assertEqual(rep["integrity_check"], "ok")
                self.assertEqual(set(rep["violations"]) - PHASE2_NOISE, set(), rep["violations"])


class Joins(unittest.TestCase):

    def test_retail_join(self):
        v = medicine_views.retail_view("MED-ASALI-001")
        self.assertTrue(v["stock"]["rows"])
        self.assertTrue(v["sales"]["rows"])
        row = v["stock"]["rows"][0]
        self.assertEqual(row["brand_name"], "Novamox 500mg")
        self.assertTrue(row["supplier_dispatch_ref"])          # business id of a DB2 shipment

    def test_distributor_join_shows_cold_chain_breach(self):
        rows = medicine_views.distributor_view("MED-ASALI-009")["shipments"]["rows"]
        self.assertTrue(rows)
        broken = [r for r in rows if r["cold_chain_maintained"] == 0]
        self.assertTrue(broken)
        self.assertTrue(all(r["excursion_readings"] > 0 for r in broken))

    def test_registry_join(self):
        row = medicine_views.registry_view("MED-ASALI-001")["registration"]["rows"][0]
        for col in ("molecule_id", "site_id", "production_id", "cert_id"):
            self.assertIsNotNone(row[col], col)
        self.assertEqual(row["generic_name"], "Amoxycillin")

    def test_ministry_join(self):
        rec = medicine_views.ministry_view("MED-RECALL-001")["recalls"]["rows"]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["recall_class"], "I")
        self.assertEqual(rec[0]["lab_result"], "fail")
        self.assertIsNotNone(rec[0]["alert_id"])
        self.assertEqual(rec[0]["parent_authority"], "Ministry of Health and Family Welfare")


class DerivedData(unittest.TestCase):

    def test_readings_agree_with_db2_cold_chain_flag(self):
        rows = sql("db2", """SELECT b.cold_chain_maintained, SUM(t.excursion) FROM distribution_batches b
                             JOIN cold_chain_loggers l ON l.batch_id = b.batch_id
                             JOIN temperature_logs t ON t.logger_id = l.logger_id GROUP BY b.batch_id""")
        self.assertTrue(rows)
        for flag, exc in rows:
            self.assertEqual(exc > 0, flag == 0)

    def test_inventory_never_exceeds_what_was_received(self):
        bad = sql("db1", """SELECT i.inventory_id FROM inventory i
                            JOIN (SELECT vendor_id, item_code, SUM(quantity_received) q FROM stock_receipts
                                  GROUP BY 1, 2) r ON r.vendor_id = i.vendor_id AND r.item_code = i.item_code
                            WHERE i.quantity_on_hand > r.q""")
        self.assertEqual(bad, [])

    def test_production_site_belongs_to_the_products_manufacturer(self):
        bad = sql("db3", """SELECT pr.production_id FROM production_records pr
                            JOIN products p ON p.product_uid = pr.product_uid
                            JOIN manufacturing_sites s ON s.site_id = pr.site_id
                            WHERE s.manufacturer_id <> p.manufacturer_id""")
        self.assertEqual(bad, [])

    def test_seeding_is_deterministic(self):
        from data import seed_phase3
        before = {(d, t): table_rows(d, t) for d, ts in NEW_TABLES.items() for t in ts}
        seed_phase3.main()
        after = {(d, t): table_rows(d, t) for d, ts in NEW_TABLES.items() for t in ts}
        self.assertEqual(before, after)


class Triggers(unittest.TestCase):

    def assertNoNewViolations(self, db):
        rep = schema_catalog.integrity_report(paths.db_path(db))
        self.assertEqual(set(rep["violations"]) - PHASE2_NOISE, set(), rep["violations"])

    def test_scan_from_unknown_terminal(self):
        sql("db1", "INSERT INTO purchase_events (event_id, scan_code, scan_timestamp, vendor_id, quantity_bought, "
                   "price_paid, device_id) VALUES ('PE-P3-T1', 'MED-ASALI-001', '2026-11-01 10:00:00', 'VND-001', 1, 240, 'POS-NEW-Z')")
        try:
            self.assertEqual(sql("db1", "SELECT vendor_id, registration_status FROM pos_terminals "
                                        "WHERE device_id = 'POS-NEW-Z'"), [("VND-001", "auto_registered")])
            self.assertNoNewViolations("db1")
        finally:
            sql("db1", "DELETE FROM purchase_events WHERE event_id = 'PE-P3-T1'")
            sql("db1", "DELETE FROM pos_terminals WHERE device_id = 'POS-NEW-Z'")

    def test_product_with_new_molecule(self):
        row = list(sql("db3", "SELECT * FROM products WHERE product_uid = 'MED-ASALI-001'")[0])
        cols = [r[1] for r in sql("db3", "PRAGMA table_info(products)")]
        row[cols.index("product_uid")] = "MED-P3TST-001"
        row[cols.index("registration_no")] = "CDSCO/P3/TEST"
        row[cols.index("generic_name")] = "Testomycin"
        sql("db3", f"INSERT INTO products VALUES ({','.join('?' * len(row))})", row)
        try:
            self.assertEqual(sql("db3", "SELECT registration_status FROM molecules WHERE generic_name = 'Testomycin'"),
                             [("auto_registered",)])
            self.assertNoNewViolations("db3")
        finally:
            sql("db3", "DELETE FROM products WHERE product_uid = 'MED-P3TST-001'")
            sql("db3", "DELETE FROM molecules WHERE generic_name = 'Testomycin'")

    def test_shipment_from_new_location(self):
        sql("db2", "INSERT INTO distribution_batches (batch_id, batch_serial, distributor_id, manufacturer_ref, "
                   "source_warehouse, destination_vendor_id, quantity_shipped, dispatch_date, status) VALUES "
                   "('DISP-P3-T1', 'MED-ASALI-001', 'DIST-001', 'MFG-001', 'Nashik Cross-dock', 'VND-001', 10, '2026-11-01', 'dispatched')")
        try:
            self.assertEqual(sql("db2", "SELECT verification_status FROM warehouses WHERE warehouse_name = 'Nashik Cross-dock'"),
                             [("auto_registered",)])
            self.assertNoNewViolations("db2")
        finally:
            sql("db2", "DELETE FROM distribution_batches WHERE batch_id = 'DISP-P3-T1'")
            sql("db2", "DELETE FROM warehouses WHERE warehouse_name = 'Nashik Cross-dock'")

    def test_officer_in_new_department(self):
        sql("db4", "INSERT INTO ministry_officers VALUES ('OFF-P3', 'Test Officer', 'State FDA Kerala', 'Inspector', NULL, NULL, 1)")
        try:
            self.assertEqual(sql("db4", "SELECT registration_status FROM regulatory_authorities "
                                        "WHERE authority_name = 'State FDA Kerala'"), [("auto_registered",)])
            self.assertNoNewViolations("db4")
        finally:
            sql("db4", "DELETE FROM ministry_officers WHERE officer_id = 'OFF-P3'")
            sql("db4", "DELETE FROM regulatory_authorities WHERE authority_name = 'State FDA Kerala'")


class Documents(unittest.TestCase):

    def test_collections_mirror_the_tables(self):
        store = os.path.dirname(paths.nosql_file())
        for name, (_f, table) in nosql_store.COLLECTIONS.items():
            with self.subTest(collection=name):
                self.assertEqual(len(nosql_store.load(store, name)), sql("db1", f"SELECT COUNT(*) FROM {table}")[0][0])

    def test_document_references_resolve(self):
        store = os.path.dirname(paths.nosql_file())
        for ref in nosql_store.check_references(store):
            if ref["kind"] != "document_reference":
                continue
            with self.subTest(ref=f"{ref['collection']}.{ref['field']}"):
                if ref["field"] == "dispensary.vendor_id":   # carries the Phase 2 mistyped vendor ids
                    self.assertLessEqual(ref["dangling"], 40)
                else:
                    self.assertEqual(ref["dangling"], 0, ref["dangling_examples"])

    def test_scan_documents_keep_their_phase2_shape(self):
        store = os.path.dirname(paths.nosql_file())
        doc = nosql_store.load(store, nosql_store.SCAN_COLLECTION)[0]
        self.assertEqual(set(doc) - {"label_capture"},
                         {"_id", "origin", "scan_code", "item_identifier", "document_type", "pos_terminal",
                          "dispensary", "transaction", "anomaly_telemetry"})


if __name__ == "__main__":
    unittest.main()
