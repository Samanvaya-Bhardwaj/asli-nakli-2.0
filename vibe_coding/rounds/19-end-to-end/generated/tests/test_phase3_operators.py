"""
Every subquery operator on both execution engines (relational SQLite and DB1's
document collections). Added after the end-to-end run found that DB1's `eq`
operator had never been exercised and failed (HTTP 500), which made the
coordinator withhold a verdict.

    python -m unittest tests.test_phase3_operators -v
"""

from __future__ import annotations
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
for k in ("ASALI_DB_DIR", "ASALI_NOSQL_FILE"):
    os.environ.pop(k, None)

from integration.federation.local_engine import NodeEngine, SubqueryError   # noqa: E402

CASES = {
    "db1": ("retail_medicines", [("_id", "eq", "MED-ASALI-009"), ("_id", "in", ["MED-ASALI-009", "MED-ASALI-001"]),
                                 ("brand_name", "contains", "basalog"), ("brand_name", "contains_any", ["basalog", "novamox"]),
                                 ("added_on", "gte", "2025-01-01"), ("added_on", "lte", "2026-12-31"),
                                 ("_id", "code", "MED-ASAL1-OO9"), ("batch.number", "eq", "BATCH-A009")]),
    "db3": ("products", [("product_uid", "eq", "MED-ASALI-009"), ("product_uid", "in", ["MED-ASALI-009", "MED-ASALI-001"]),
                         ("product_name", "contains", "basalog"), ("product_name", "contains_any", ["basalog", "novamox"]),
                         ("manufacture_date", "gte", "2025-01-01"), ("manufacture_date", "lte", "2026-12-31"),
                         ("product_uid", "code", "MED-ASAL1-OO9"), ("batch_number", "eq", "BATCH-A009")]),
}


class Operators(unittest.TestCase):

    def test_every_operator_on_both_engines(self):
        for db, (target, conds) in CASES.items():
            eng = NodeEngine(db)
            for field, op, value in conds:
                with self.subTest(db=db, op=op, field=field):
                    r = eng.run({"target": target, "where": [{"field": field, "op": op, "value": value}],
                                 "expand": {"max_augmentation": 0}})
                    self.assertTrue(r["matches"], (db, op, field))
                    self.assertTrue(r["native_query"])

    def test_combined_conditions(self):
        for db, (target, _c) in CASES.items():
            key = "_id" if db == "db1" else "product_uid"
            batch = "batch.number" if db == "db1" else "batch_number"
            r = NodeEngine(db).run({"target": target, "combine": "all", "expand": {"max_augmentation": 0},
                                    "where": [{"field": key, "op": "code", "value": "MED-ASALI-009"},
                                              {"field": batch, "op": "eq", "value": "BATCH-A009"}]})
            self.assertEqual(len(r["matches"]), 1, db)
            r = NodeEngine(db).run({"target": target, "combine": "all", "expand": {"max_augmentation": 0},
                                    "where": [{"field": key, "op": "code", "value": "MED-ASALI-009"},
                                              {"field": batch, "op": "eq", "value": "BATCH-A001"}]})
            self.assertEqual(r["matches"], [], db)

    def test_unknown_operator_and_field_are_refused(self):
        eng = NodeEngine("db1")
        with self.assertRaises(SubqueryError):
            eng.run({"target": "retail_medicines", "where": [{"field": "_id", "op": "regex", "value": "x"}]})
        with self.assertRaises(SubqueryError):
            eng.run({"target": "retail_medicines", "where": [{"field": "$where", "op": "eq", "value": "x"}]})


if __name__ == "__main__":
    unittest.main()
