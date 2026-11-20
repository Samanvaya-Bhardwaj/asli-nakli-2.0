"""
Phase 3: SCORE-inspired query context discovery (integration/federation/score_context.py)
and its aggregation (context_aggregator.py).

Runs the database-local algorithm directly on throwaway copies of the four
databases (the same code each database service runs), so every check is about
the algorithm itself:

    python -m unittest tests.test_phase3_score -v
"""

from __future__ import annotations
import os
import shutil
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
TMP = tempfile.mkdtemp(prefix="asali_score_")
os.environ["ASALI_DB_DIR"] = os.path.join(TMP, "databases")
os.environ["ASALI_NOSQL_FILE"] = os.path.join(TMP, "nosql_store", "db1_retail_pos.json")

from integration.federation import schema_catalog                     # noqa: E402
from integration.federation.context_aggregator import aggregate       # noqa: E402
from integration.federation.local_engine import NodeEngine            # noqa: E402
from integration.uncertainty import paths                             # noqa: E402

COLD = ["cold chain", "temperature", "excursion", "refrigerat", "storage"]
RECALL = ["recall", "withdrawn", "banned", "blacklist"]


def setUpModule():
    os.makedirs(paths.db_dir())
    for f in ("db1_purchase_registry", "db2_distributor_ledger", "db3_manufacturer_registry", "db4_ministry_reports"):
        shutil.copy2(os.path.join(BASE, "databases", f + ".sqlite"), paths.db_dir())
    shutil.copytree(os.path.join(BASE, "data", "nosql_store"), os.path.dirname(paths.nosql_file()))


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def run(db, target, field, value, keywords=(), op="code", **expand):
    return NodeEngine(db).run({"id": "t", "target": target, "where": [{"field": field, "op": op, "value": value}],
                               "expand": {"keywords": list(keywords), **expand}})


class Algorithm(unittest.TestCase):

    def test_only_real_foreign_keys_are_joined(self):
        real = set()
        for fk in schema_catalog.fk_edges(paths.db_path("db2")):
            real.add(f"{fk.table}({', '.join(fk.columns)}) -> {fk.ref_table}({', '.join(fk.ref_columns)})")
            real.add(f"{fk.ref_table}({', '.join(fk.ref_columns)}) -> {fk.table}({', '.join(fk.columns)})")
        sc = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009", COLD)["score_context"]
        self.assertTrue(sc["joins_performed"])
        for j in sc["joins_performed"]:
            self.assertIn(j["fk"], real)
            self.assertIn(" JOIN ", j["join"])
        self.assertEqual(len(sc["schema_graph"]["edges"]), len(schema_catalog.fk_edges(paths.db_path("db2"))))

    def test_max_augmentation_and_top_n(self):
        for limit in (0, 1, 2, 3):
            r = run("db3", "products", "product_uid", "MED-ASALI-009", COLD, max_augmentation=limit, top_n=7)
            sc = r["score_context"]
            if limit == 0:
                self.assertIsNone(sc)
                continue
            self.assertLessEqual(len(sc["joins_performed"]), limit)
            self.assertLessEqual(len(sc["ranked_context"]), 7)
            self.assertEqual(len(sc["explored_tables"]), 1 + len(sc["joins_performed"]))

    def test_query_relevance_decides_which_fk_is_joined_first(self):
        cold = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009", COLD)["score_context"]
        self.assertEqual(cold["joins_performed"][0]["to"], "cold_chain_loggers")
        recall = run("db4", "complaints", "complaint_item_ref", "MED-RECALL-001", RECALL)["score_context"]
        self.assertIn(recall["joins_performed"][0]["to"], ("ministry_blacklist", "recall_notices"))
        plain = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009")["score_context"]
        aff = {c["to"]: c["schema_affinity"] for c in plain["augmentation"][0]["candidates"]}
        self.assertEqual(aff["cold_chain_loggers"], 0.0)          # no question, no affinity

    def test_rare_values_outrank_common_ones(self):
        # no query words: this is the tf x idf weighting alone, over the full ranking
        sc = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009", top_n=100)["score_context"]
        terms = {t["key"]: t for t in sc["ranked_context"]}
        # every shipment is 'delivered'; only 45 of 427 broke the cold chain
        breach = terms["categorical:cold_chain_maintained=0"]
        delivered = terms["categorical:status=delivered"]
        self.assertGreater(breach["score"], 5 * delivered["score"])

    def test_unrelated_tables_are_not_explored(self):
        sc = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009", COLD, max_augmentation=8)["score_context"]
        explored = set(sc["explored_tables"])
        self.assertNotIn("return_log", explored)                 # no FK at all
        for st in sc["augmentation"]:
            for c in st["candidates"]:
                if c["new_terms"] == 0 or c["joined_rows"] == 0:
                    self.assertEqual(c["fk_relevance"], 0.0)
                    self.assertFalse(c.get("chosen"))
        strict = run("db2", "distribution_batches", "batch_serial", "MED-ASALI-009", COLD,
                     min_fk_relevance=1000)["score_context"]
        self.assertEqual(strict["joins_performed"], [])
        self.assertIn("no neighbouring table adds relevant context", strict["stop_reason"])

    def test_every_term_keeps_its_provenance(self):
        sc = run("db3", "products", "product_uid", "MED-ASALI-009", COLD)["score_context"]
        for t in sc["ranked_context"]:
            self.assertEqual(t["source"]["database"], "db3")
            self.assertIn(t["source"]["table"], sc["explored_tables"])
            self.assertTrue(t["source"]["column"])
            self.assertTrue(t["relationship_path"])
            self.assertTrue(t["entities"])
        joined = [t for t in sc["ranked_context"] if t["relationship_path"] != ["(query result)"]]
        self.assertTrue(joined)

    def test_document_store_joins_follow_declared_references(self):
        sc = run("db1", "retail_medicines", "_id", "MED-ASALI-001", ["stock", "inventory", "received"])["score_context"]
        self.assertTrue(sc["joins_performed"])
        self.assertTrue(all("$lookup" in j["join"] for j in sc["joins_performed"]))
        self.assertTrue({"stock_receipts", "inventory"} <= set(sc["explored_tables"]))
        kinds = {e["kind"] for e in sc["schema_graph"]["edges"]}
        self.assertIn("document_reference", kinds)

    def test_entity_matching_only_chooses_the_result_rows(self):
        r = run("db3", "products", "product_uid", "MED-ASAL1-OO9", COLD)        # damaged code
        self.assertEqual([m["match"] for m in r["matches"]], ["lookalike"])
        clean = run("db3", "products", "product_uid", "MED-ASALI-009", COLD)
        self.assertEqual([t["key"] for t in r["score_context"]["ranked_context"]],
                         [t["key"] for t in clean["score_context"]["ranked_context"]])

    def test_deterministic(self):
        a = run("db4", "recall_notices", "item_ref", "MED-RECALL-001", RECALL)["score_context"]
        b = run("db4", "recall_notices", "item_ref", "MED-RECALL-001", RECALL)["score_context"]
        self.assertEqual(a["ranked_context"], b["ranked_context"])
        self.assertEqual(a["joins_performed"], b["joins_performed"])


class Aggregation(unittest.TestCase):

    def per_db(self):
        out = {}
        for d, args in {"db2": ("distribution_batches", "batch_serial"), "db3": ("products", "product_uid")}.items():
            r = run(d, args[0], args[1], "MED-ASALI-009", COLD)
            r["subquery_id"] = f"T.{d}.1"
            out[d] = {"subqueries": [r]}
        return out

    def test_identifiers_are_merged_across_databases(self):
        agg = aggregate(self.per_db(), top_n=200)
        mfg = next(t for t in agg["terms"] if t["key"] == "id:MFG-004")
        self.assertEqual(mfg["databases"], ["db2", "db3"])
        self.assertEqual({p["database"] for p in mfg["provenance"]}, {"db2", "db3"})
        self.assertIn("found independently by 2 databases (db2, db3)", mfg["why_relevant"])
        self.assertEqual(len({t["key"] for t in agg["terms"]}), len(agg["terms"]))

    def test_the_question_itself_is_an_anchor_not_context(self):
        agg = aggregate(self.per_db(), top_n=200, anchors=["MED-ASALI-009"])
        self.assertNotIn("id:MED-ASALI-009", {t["key"] for t in agg["terms"]})
        self.assertEqual(agg["anchors"][0]["databases"], ["db2", "db3"])

    def test_ranking_and_explanations(self):
        agg = aggregate(self.per_db(), top_n=10)
        scores = [t["score"] for t in agg["terms"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(t["why_relevant"] for t in agg["terms"]))
        self.assertTrue(any(t["query_match"] for t in agg["terms"][:5]))


if __name__ == "__main__":
    unittest.main()
