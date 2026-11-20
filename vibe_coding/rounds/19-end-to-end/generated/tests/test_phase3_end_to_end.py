"""
Phase 3 end to end, exactly as a user meets it: four database services and the
coordinator service, each its own process with its own data directory, driven
only over HTTP (the coordinator's page and /api/v3/federated/query).

Checks the ten steps of the Phase 3 workflow on the three demonstration
scenarios, the page, and a database dying mid-session. Local simulation (one
machine, loopback): process and data isolation, not multi-machine execution.

    python -m unittest tests.test_phase3_end_to_end -v
"""

from __future__ import annotations
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="asali_e2e_")
DBS = ("db1", "db2", "db3", "db4")
PROCS, PORTS = {}, {}
TOKENS = {d: secrets.token_urlsafe(16) for d in DBS}

S1 = "Is MED-ASALI-009 from batch BATCH-A009 genuine?"
S2 = "Any quality or safety concerns about products manufactured by MFG-002 (Sun Pharmaceutical)?"
S3 = "Are there consumer complaints or regulatory action against MED-NAKALI-001?"
RESULTS = {}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def env_for(extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ASALI_")}
    env.update({"PYTHONIOENCODING": "utf-8", "ASALI_NODE_BIND": "127.0.0.1", "ASALI_MACHINE_LABEL": "e2e-simulation"})
    env.update(extra)
    return env


def start_node(d):
    own = os.path.join(TMP, "nodes", d)
    PROCS[d] = subprocess.Popen([PY, os.path.join(BASE, "api", "node_db.py"), "--db", d], cwd=BASE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_for({
                                    "ASALI_DB_DIR": os.path.join(own, "databases"),
                                    "ASALI_NOSQL_FILE": os.path.join(own, "nosql_store", "db1_retail_pos.json"),
                                    "ASALI_DOCS_DIR": os.path.join(own, "documents"),
                                    f"ASALI_{d.upper()}_PORT": str(PORTS[d]), f"ASALI_{d.upper()}_TOKEN": TOKENS[d]}))


def http(path, body=None, port=None, timeout=120):
    req = urllib.request.Request(f"http://127.0.0.1:{port or PORTS['coordinator']}{path}",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if r.headers.get_content_type() == "application/json" else raw.decode("utf-8"))


def wait(port, path="/health", timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return http(path, port=port, timeout=2)
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"port {port} did not answer")


def setUpModule():
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import prepare_node_data
    for d in DBS:
        prepare_node_data.prepare(d, os.path.join(TMP, "nodes"), os.path.join(BASE, "databases"),
                                  os.path.join(BASE, "data", "nosql_store"))
        PORTS[d] = free_port()
        start_node(d)
    PORTS["coordinator"] = free_port()
    cenv = {"ASALI_DB_DIR": os.path.join(TMP, "coordinator-state"),
            "ASALI_NOSQL_FILE": os.path.join(TMP, "coordinator-state", "none.json"),
            "ASALI_COORDINATOR_BIND": "127.0.0.1", "ASALI_COORDINATOR_PORT": str(PORTS["coordinator"]),
            "ASALI_NODE_TIMEOUT_SEC": "8"}
    for d in DBS:
        cenv.update({f"ASALI_{d.upper()}_URL": f"http://127.0.0.1:{PORTS[d]}", f"ASALI_{d.upper()}_TOKEN": TOKENS[d],
                     f"ASALI_{d.upper()}_MACHINE": "e2e-simulation"})
    os.makedirs(cenv["ASALI_DB_DIR"])
    for d in DBS:
        wait(PORTS[d])
    PROCS["coordinator"] = subprocess.Popen([PY, os.path.join(BASE, "api", "coordinator_service.py")], cwd=BASE,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_for(cenv))
    wait(PORTS["coordinator"])
    for q in (S1, S2, S3):
        RESULTS[q] = http("/api/v3/federated/query", {"query": q})[1]


def tearDownModule():
    for p in PROCS.values():
        p.terminate()
    for p in PROCS.values():
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    shutil.rmtree(TMP, ignore_errors=True)


class Workflow(unittest.TestCase):

    def test_0_the_page_is_served_by_the_coordinator(self):
        status, page = http("/")
        self.assertEqual(status, 200)
        self.assertIn("Ask the federation", page)
        self.assertIn("/api/v3/federated/query", page)

    def test_1_2_question_interpreted_and_unfolded_into_database_subqueries(self):
        r = RESULTS[S1]
        self.assertEqual(r["understanding"]["item_codes"], ["MED-ASALI-009"])
        self.assertEqual(r["understanding"]["batch_numbers"], ["BATCH-A009"])
        self.assertEqual(r["routing"]["databases"], list(DBS))
        targets = {d: {s["target"] for s in subs} for d, subs in r["subqueries"].items()}
        self.assertIn("products", targets["db3"])
        self.assertIn("distribution_batches", targets["db2"])
        self.assertIn("retail_pos_scans", targets["db1"])
        self.assertIn("complaints", targets["db4"])

    def test_3_4_federated_and_executed_by_each_database_process(self):
        r = RESULTS[S1]
        self.assertEqual(r["source_status"], {d: "ok" for d in DBS})
        for d in DBS:
            self.assertEqual(r["sources"][d]["served_by"]["pid"], PROCS[d].pid)
            self.assertTrue(all(sq["database"] == d for sq in r["sources"][d]["subqueries"]))
        self.assertTrue(r["sources"]["db1"]["subqueries"][0]["native_query"].startswith("db.retail_pos_scans.find("))
        self.assertIn("SELECT", r["sources"]["db3"]["subqueries"][0]["native_query"])

    def test_5_6_each_database_discovers_and_returns_its_own_context(self):
        r = RESULTS[S1]
        for d in ("db1", "db2", "db3"):
            sc = next(sq["score_context"] for sq in r["sources"][d]["subqueries"] if sq["score_context"])
            self.assertTrue(sc["joins_performed"], d)
            self.assertTrue(sc["ranked_context"], d)
            self.assertTrue(all(t["source"]["database"] == d for t in sc["ranked_context"]))
            beyond = [t for t in sc["ranked_context"] if t["relationship_path"] != ["(query result)"]]
            self.assertTrue(beyond, f"{d}: no context beyond the query result")

    def test_7_mediator_aggregates_the_local_contexts(self):
        qc = RESULTS[S1]["query_context"]
        self.assertGreaterEqual(len(qc["databases_contributing"]), 3)
        self.assertTrue(any(len(t["databases"]) > 1 for t in qc["terms"]))      # deduplicated across databases
        self.assertIn("MED-ASALI-009", {a["term"] for a in qc["anchors"]})

    def test_8_9_document_search_is_built_from_the_context(self):
        req = RESULTS[S2]["document_search"]["request"]
        ctx_ids = [e for e in req["entities"] if not e["anchor"]]
        self.assertTrue(ctx_ids)                              # identifiers found through FK joins
        self.assertTrue(req["context_terms"])
        docs = RESULTS[S2]["document_search"]["documents"]
        self.assertTrue(docs)
        self.assertEqual([d["score"] for d in docs], sorted((d["score"] for d in docs), reverse=True))
        # a recall the question never mentioned, reached through the manufacturer's products
        self.assertTrue(any(d["type"] == "recall_notice" for d in docs))

    def test_10_integrated_response(self):
        for q in (S1, S2, S3):
            i = RESULTS[q]["integrated"]
            self.assertEqual({k for k in i if k[1] == "_"} - {"F_G_H"},
                             {"A_question", "B_structured_results", "C_local_context", "D_aggregated_context", "E_documents"})
            for d in i["E_documents"]:
                self.assertTrue(d["provenance"]["database"] and d["provenance"]["file"])
                self.assertTrue(d["why_retrieved"])
        v = RESULTS[S1]["verdicts"][0]
        self.assertEqual((v["status"], v["verdict"], v["trust_score"]), ("COMPUTED", "SUSPICIOUS", 65))
        v3 = RESULTS[S3]["verdicts"][0]
        self.assertEqual(v3["verdict"], "NAKALI")
        allegations = [d for d in RESULTS[S3]["integrated"]["E_documents"] if "not verified" in d["evidence_status"]]
        self.assertTrue(allegations and all("caution" in d for d in allegations))

    def test_scenarios_differ(self):
        tops = [{d["doc_id"] for d in RESULTS[q]["integrated"]["E_documents"][:5]} for q in (S1, S2, S3)]
        self.assertFalse(tops[0] & tops[1] or tops[0] & tops[2] or tops[1] & tops[2])

    def test_z_a_database_dies_mid_session(self):
        PROCS["db3"].terminate()
        PROCS["db3"].wait(timeout=10)
        try:
            r = http("/api/v3/federated/query", {"query": S1})[1]
            self.assertEqual(r["source_status"]["db3"], "unreachable")
            self.assertTrue(all(r["source_status"][d] == "ok" for d in ("db1", "db2", "db4")))
            self.assertTrue(r["partial"])
            self.assertEqual(r["verdicts"][0]["status"], "WITHHELD")
            self.assertEqual(r["document_search"]["per_database"]["db3"]["status"], "unreachable")
            self.assertTrue(r["document_search"]["documents"])      # the other sources' documents still come back
            self.assertTrue(all(d["owner_database"] != "db3" for d in r["document_search"]["documents"]))
        finally:
            start_node("db3")
            wait(PORTS["db3"])
        r = http("/api/v3/federated/query", {"query": S1})[1]
        self.assertEqual(r["verdicts"][0]["status"], "COMPUTED")          # recovers when it comes back


if __name__ == "__main__":
    unittest.main()
