"""
Phase 3: unstructured documents - ingestion, context-aware retrieval and the
integrated structured + unstructured response.

Uses the project's databases and documents read-only, running the pipeline
in-process (scripts/eval_retrieval.run_inprocess: the code each service runs,
without HTTP).

    python -m unittest tests.test_phase3_documents -v
"""

from __future__ import annotations
import json
import os
import sqlite3
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))
os.environ.pop("ASALI_DOCS_DIR", None)

from integration.federation.doc_store import chunk, docs_dir, store       # noqa: E402
from integration.federation.retrieval import integrated_response          # noqa: E402
from integration.uncertainty.context import fold                          # noqa: E402
import eval_retrieval                                                     # noqa: E402

GT = json.load(open(os.path.join(BASE, "data", "documents", "ground_truth.json"), encoding="utf-8"))["documents"]
DBS = ("db1", "db2", "db3", "db4")


def ids(results):
    return [r["doc_id"] for r in results]


class Ingestion(unittest.TestCase):

    def test_every_document_is_ingested_with_metadata(self):
        n = sum(len(store(d).docs) for d in DBS)
        self.assertEqual(n, len(GT))
        for d in DBS:
            for doc in store(d).docs.values():
                m = doc.metadata()
                for k in ("doc_id", "title", "type", "source", "date", "owner_database", "medicine_ids",
                          "batch_ids", "manufacturer_ids"):
                    self.assertIn(k, m)
                self.assertEqual(m["owner_database"], d)
                self.assertEqual(m["type"], GT[m["doc_id"]]["type"])

    def test_html_text_is_extracted(self):
        rcl = store("db4").docs["DOC-DB4-RCL-001"]
        self.assertEqual(rcl.fmt, "html")
        self.assertTrue(rcl.title.startswith("Recall notice"))
        self.assertNotIn("<p>", " ".join(c.text for c in rcl.chunks))
        self.assertEqual(rcl.date, "2025-05-20")

    def test_dates_in_any_format_are_normalised(self):
        dated = [d for s in DBS for d in store(s).docs.values() if d.date]
        self.assertGreater(len(dated) / len(GT), 0.95)
        self.assertTrue(any("/" in d.date_raw for d in dated) and any(d.date_raw[:1].isalpha() for d in dated))

    def test_long_documents_are_chunked(self):
        self.assertTrue(any(len(d.chunks) > 1 for d in store("db3").docs.values()))
        parts = chunk(" ".join(f"w{i}" for i in range(300)))
        self.assertGreater(len(parts), 2)
        self.assertTrue(all(len(p.split()) <= 120 for p in parts))

    def test_entity_extraction_against_ground_truth(self):
        tp = fn = fp = 0
        for d in DBS:
            for doc in store(d).docs.values():
                truth, got = set(GT[doc.doc_id]["item_codes"]), doc.entities.get("item_code", [])
                for t in truth:
                    if any(g["value"] == t or g["fold"] == fold(t) for g in got):
                        tp += 1
                    else:
                        fn += 1
                fp += sum(1 for g in got if not any(g["value"] == t or g["fold"] == fold(t) for t in truth))
        self.assertGreater(tp / (tp + fn), 0.88)
        self.assertGreater(tp / (tp + fp), 0.9)

    def test_documents_are_files_not_database_rows(self):
        letter = store("db4").docs["DOC-DB4-CCL-001"]
        self.assertTrue(os.path.exists(os.path.join(docs_dir("db4"), letter.file)))
        conn = sqlite3.connect(f"file:{os.path.join(BASE, 'databases', 'db4_ministry_reports.sqlite')}?mode=ro", uri=True)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM complaints WHERE description LIKE '%Please look into this%'")
                         .fetchone()[0], 0)
        conn.close()


class Retrieval(unittest.TestCase):

    def test_context_finds_what_the_question_alone_misses(self):
        q = "Find information about batch BATCH-A009 manufactured by Biocon and identify any quality or safety concerns"
        req, with_ctx, _ = eval_retrieval.run_inprocess(q, True)
        _r, plain, _ = eval_retrieval.run_inprocess(q, False)
        # the batch's pack code was found only through the FK context (products -> batch_number);
        # the shipment note names the pack code, never the batch, so only the context reaches it
        self.assertIn("MED-ASALI-009", {e["value"] for e in req["entities"] if e["kind"] == "item_code"})
        self.assertNotIn("BATCH-A009", store("db2").docs["DOC-DB2-SHP-003"].metadata()["batch_ids"])
        self.assertIn("DOC-DB2-SHP-003", ids(with_ctx))
        self.assertNotIn("DOC-DB2-SHP-003", ids(plain))
        self.assertGreater(len(with_ctx), len(plain))

    def test_different_questions_retrieve_different_documents(self):
        tops = [set(ids(eval_retrieval.run_inprocess(q, True)[1][:5])) for q in (
            "Was the cold chain of MED-ASALI-009 maintained?", "Has MED-RECALL-001 been recalled, and why?",
            "Is MED-NAKALI-001 counterfeit?")]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertFalse(tops[i] & tops[j])

    def test_a_sibling_batch_one_character_away_is_not_retrieved(self):
        _req, res, _ = eval_retrieval.run_inprocess("Was the cold chain of MED-ASALI-009 maintained?", True)
        for r in res:
            codes = set(r["medicine_ids"])
            if codes:
                self.assertIn("MED-ASALI-009", codes, (r["doc_id"], codes))

    def test_sharing_common_words_is_not_enough(self):
        res = store("db3").search({"query_text": "quality report ltd", "entities": [], "context_terms": [],
                                   "intents": []})
        self.assertEqual(res["results"], [])

    def test_a_damaged_code_in_a_document_still_links(self):
        damaged = [(d, doc) for d in DBS for doc in store(d).docs.values()
                   for e in doc.entities.get("item_code", []) if e["raw"].upper() != e["value"]
                   and e["value"] in GT[doc.doc_id]["item_codes"]]
        self.assertTrue(damaged)
        d, doc = damaged[0]
        code = next(e for e in doc.entities["item_code"] if e["raw"].upper() != e["value"])["value"]
        res = store(d).search({"query_text": "", "entities": [{"kind": "item_code", "value": code, "weight": 1.0,
                                                               "anchor": True}], "context_terms": [], "intents": []})
        self.assertIn(doc.doc_id, ids(res["results"]))

    def test_every_result_explains_itself(self):
        _req, res, _ = eval_retrieval.run_inprocess("Has MED-RECALL-001 been recalled, and why?", True)
        self.assertTrue(res)
        for r in res:
            self.assertTrue(r["why_retrieved"])
            self.assertIn("lexical", r["score_parts"])
            self.assertTrue(r["evidence_status"])
        scores = [r["score"] for r in res]
        self.assertEqual(scores, sorted(scores, reverse=True))


class Integration(unittest.TestCase):

    def test_unverified_complaints_are_marked_as_allegations(self):
        _req, res, qc = eval_retrieval.run_inprocess("Is MED-NAKALI-001 counterfeit?", True)
        fake = {"question": "Is MED-NAKALI-001 counterfeit?", "sources": {}, "verdicts": [],
                "combined": {"medicines": [], "cross_source_links": []}, "query_context": qc,
                "document_search": {"documents": res}}
        out = integrated_response(fake)
        complaints = [d for d in out["E_documents"] if "not verified" in d["evidence_status"]]
        self.assertTrue(complaints)
        self.assertTrue(all("not proof" in d.get("caution", "not proof") for d in complaints))
        self.assertIn("never change the verdict", out["policy"])
        self.assertEqual(set(k[0] for k in out if k[1] == "_"), {"A", "B", "C", "D", "E", "F"})


if __name__ == "__main__":
    unittest.main()
