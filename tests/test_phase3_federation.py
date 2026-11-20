"""
Phase 3, Requirement 2: distributed database services and federated queries.

Starts the four database services as separate processes, each with a data
directory holding only its own database (copied from this project), then runs
the coordinator in this process in federated mode and checks isolation,
authentication, local execution and discovery, routing, partial results,
timeouts, and that verdicts over the network equal Phase 1 local verdicts.

All of this is on one machine (loopback): it shows process and data isolation,
not multi-machine execution. Run it on its own (it sets ASALI_FEDERATION=remote
for its process):

    python -m unittest tests.test_phase3_federation -v
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
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
PY = sys.executable
TMP = tempfile.mkdtemp(prefix="asali_fed_")
NODES_DIR, FULL_DIR, STATE_DIR = (os.path.join(TMP, x) for x in ("nodes", "full", "state"))
DBS = ("db1", "db2", "db3", "db4")
PROCS = {}
PORTS = {}
TOKENS = {d: secrets.token_urlsafe(16) for d in DBS}
CURATED = ["MED-ASALI-001", "MED-ASALI-002", "MED-ASALI-003", "MED-ASALI-004", "MED-ASALI-005", "MED-ASALI-006",
           "MED-ASALI-007", "MED-ASALI-008", "MED-ASALI-009", "MED-ASALI-010", "MED-NAKALI-001", "MED-NAKALI-002",
           "MED-NAKALI-003", "MED-NAKALI-004", "MED-NAKALI-005", "MED-RECALL-001", "MED-RECALL-002",
           "MED-RECALL-003", "MED-UNAUTH-001", "MED-UNAUTH-002", "MED-ASAL1-OO1", "BATCH-A001", "Novamox",
           "MED-TOTALLY-FAKE-9999", "MED-ASALI-999"]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def node_env(d, data_dir, port, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ASALI_")}
    env.update({"ASALI_DB_DIR": os.path.join(data_dir, "databases"),
                "ASALI_NOSQL_FILE": os.path.join(data_dir, "nosql_store", "db1_retail_pos.json"),
                "ASALI_NODE_BIND": "127.0.0.1", f"ASALI_{d.upper()}_PORT": str(port),
                f"ASALI_{d.upper()}_TOKEN": TOKENS[d], "ASALI_MACHINE_LABEL": "test-simulation",
                "PYTHONIOENCODING": "utf-8"})
    env.update(extra)
    return env


def start(d, data_dir, port, capture=False, **extra):
    # services run for the whole module: never leave them writing into an undrained pipe
    return subprocess.Popen([PY, os.path.join(BASE, "api", "node_db.py"), "--db", d],
                            env=node_env(d, data_dir, port, **extra), cwd=BASE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE if capture else subprocess.DEVNULL)


def http(url, body=None, token=None, timeout=10):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def wait_up(port, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return http(f"http://127.0.0.1:{port}/health", timeout=1)[1]
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"service on {port} did not come up")


def setUpModule():
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import prepare_node_data
    src_db, src_nosql = os.path.join(BASE, "databases"), os.path.join(BASE, "data", "nosql_store")
    for d in DBS:
        prepare_node_data.prepare(d, NODES_DIR, src_db, src_nosql)
    # a full copy, for the local-mode reference verdicts and the isolation test
    os.makedirs(os.path.join(FULL_DIR, "databases"))
    for d in DBS:
        shutil.copy2(os.path.join(NODES_DIR, d, "databases", prepare_node_data.FILES[d]),
                     os.path.join(FULL_DIR, "databases"))
    shutil.copytree(os.path.join(NODES_DIR, "db1", "nosql_store"), os.path.join(FULL_DIR, "nosql_store"))
    for d in DBS:
        PORTS[d] = free_port()
        PROCS[d] = start(d, os.path.join(NODES_DIR, d), PORTS[d])
    PORTS["slow_db4"] = free_port()
    PROCS["slow_db4"] = start("db4", os.path.join(NODES_DIR, "db4"), PORTS["slow_db4"], ASALI_NODE_DELAY_SEC="3")
    for k in PORTS:
        wait_up(PORTS[k])
    # this process is the coordinator: federated mode, no database files of its own
    os.makedirs(STATE_DIR)
    os.environ.update({"ASALI_FEDERATION": "remote", "ASALI_DB_DIR": STATE_DIR,
                       "ASALI_NOSQL_FILE": os.path.join(STATE_DIR, "none.json"), "ASALI_NODE_TIMEOUT_SEC": "6"})
    for d in DBS:
        os.environ[f"ASALI_{d.upper()}_URL"] = f"http://127.0.0.1:{PORTS[d]}"
        os.environ[f"ASALI_{d.upper()}_TOKEN"] = TOKENS[d]
        os.environ[f"ASALI_{d.upper()}_MACHINE"] = "test-simulation"


def tearDownModule():
    for p in PROCS.values():
        p.terminate()
    for p in PROCS.values():
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    shutil.rmtree(TMP, ignore_errors=True)


def url(d):
    return f"http://127.0.0.1:{PORTS[d]}"


def subquery(d, sq):
    status, body = http(url(d) + "/api/v3/subquery", {"subquery": sq}, TOKENS[d])
    if d == "db4" and status == 200:
        body = body["data"]                          # DB4 keeps its REST envelope
    return status, body


class Deployment(unittest.TestCase):

    def test_four_independent_processes_each_with_only_its_own_data(self):
        pids = set()
        for d in DBS:
            h = http(url(d) + "/health")[1]
            self.assertEqual(h["database"], d)
            self.assertEqual(h["isolation"]["foreign_files_visible"], 0)
            self.assertTrue(all(f["present"] for f in h["data_files"]))
            pids.add(h["pid"])
        self.assertEqual(len(pids), 4)
        self.assertNotIn(os.getpid(), pids)

    def test_service_refuses_a_directory_holding_other_databases(self):
        p = start("db2", FULL_DIR, free_port(), capture=True)
        _out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 3)
        self.assertIn(b"other databases", err)

    def test_service_refuses_to_start_without_a_token(self):
        env = node_env("db3", os.path.join(NODES_DIR, "db3"), free_port())
        env.pop("ASALI_DB3_TOKEN")
        p = subprocess.run([PY, os.path.join(BASE, "api", "node_db.py"), "--db", "db3"], env=env, cwd=BASE,
                           capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 2)

    def test_every_data_endpoint_requires_the_token(self):
        for d in DBS:
            self.assertEqual(http(url(d) + "/api/v3/schema")[0], 401)
            self.assertEqual(http(url(d) + "/api/v3/schema", token="wrong")[0], 401)
            self.assertEqual(http(url(d) + "/api/v3/subquery", {"subquery": {}}, token=TOKENS["db1" if d != "db1" else "db2"])[0], 401)

    def test_coordinator_classifies_this_as_a_local_simulation(self):
        from integration.federation.coordinator import nodes_status
        st = nodes_status()
        self.assertEqual(st["deployment"]["mode"], "LOCAL_SIMULATION")
        self.assertTrue(all(n["status"] == "online" for n in st["nodes"].values()))


class LocalExecution(unittest.TestCase):

    def test_schema_exposes_keys_and_relationships(self):
        s = http(url("db2") + "/api/v3/schema", token=TOKENS["db2"])[1]["schema"]
        self.assertIn(["distributor_id", "source_warehouse"], [r["child_columns"] for r in s["relationships"]])
        s1 = http(url("db1") + "/api/v3/schema", token=TOKENS["db1"])[1]["schema"]
        self.assertTrue(s1["paradigm"].startswith("document"))
        self.assertIn("document_reference", {r["kind"] for r in s1["relationships"]})
        self.assertIn("relationships", s1["authoritative_sqlite"])
        status, raw = http(url("db4") + "/api/v3/schema", token=TOKENS["db4"])
        self.assertEqual(set(raw), {"meta", "data"})

    def test_subqueries_are_checked_against_the_local_schema(self):
        self.assertEqual(subquery("db3", {"target": "sqlite_master"})[0], 400)
        self.assertEqual(subquery("db3", {"target": "products", "where": [
            {"field": "product_uid = '' OR 1=1 --", "op": "eq", "value": "x"}]})[0], 400)
        self.assertEqual(subquery("db2", {"target": "products"})[0], 400)    # DB3's table, not DB2's
        self.assertEqual(subquery("db3", {"target": "products", "where": [
            {"field": "product_uid", "op": "drop", "value": 1}]})[0], 400)

    def test_each_database_discovers_context_through_its_own_keys(self):
        db3_tables = set(http(url("db3") + "/api/v3/schema", token=TOKENS["db3"])[1]["schema"]["tables"])
        where = [{"field": "product_uid", "op": "code", "value": "MED-ASALI-009"}]
        # the plain walk (Requirement 2 baseline) visits every neighbour within two hops
        status, body = subquery("db3", {"id": "t", "target": "products", "where": where,
                                        "expand": {"max_hops": 2, "method": "bfs"}})
        self.assertEqual(status, 200)
        r = body["result"]
        self.assertEqual(len(r["matches"]), 1)
        bfs_tables = {c["table"] for c in r["context"]}
        self.assertTrue({"production_records", "manufacturing_sites", "molecules", "batch_release_certs"} <= bfs_tables)
        self.assertTrue(bfs_tables <= db3_tables)          # nothing from any other database
        self.assertTrue(all(c["path"] for c in r["context"]))
        self.assertIn("SELECT", r["native_query"])
        # SCORE (the default) joins selectively, still only within this database
        r = subquery("db3", {"id": "t", "target": "products", "where": where,
                             "expand": {"keywords": ["cold chain"], "max_augmentation": 3}})[1]["result"]
        self.assertEqual(r["context_method"], "score")
        explored = set(r["score_context"]["explored_tables"])
        self.assertLessEqual(len(explored), 4)
        self.assertTrue(explored <= db3_tables)
        self.assertTrue(all(c["path"] for c in r["context"]))

    def test_document_store_answers_with_a_document_query(self):
        status, body = subquery("db1", {"id": "t", "target": "retail_pos_scans",
                                        "where": [{"field": "scan_code", "op": "code", "value": "MED-ASALI-009"}],
                                        "expand": {"max_hops": 1, "method": "bfs"}})
        r = body["result"]
        self.assertTrue(r["native_query"].startswith("db.retail_pos_scans.find("))
        self.assertIn("pos_terminals", r["context_summary"])
        r = subquery("db1", {"id": "t", "target": "retail_pos_scans",
                             "where": [{"field": "scan_code", "op": "code", "value": "MED-ASALI-009"}]})[1]["result"]
        self.assertTrue(all("$lookup" in j["join"] for j in r["score_context"]["joins_performed"]))

    def test_damaged_code_and_one_edit_neighbours(self):
        r = subquery("db3", {"target": "products", "where": [
            {"field": "product_uid", "op": "code", "value": "MED-ASAL1-OO9"}]})[1]["result"]
        self.assertEqual([(m["row"]["product_uid"], m["match"]) for m in r["matches"]], [("MED-ASALI-009", "lookalike")])
        r = subquery("db3", {"target": "products", "where": [
            {"field": "product_uid", "op": "code", "value": "MED-ASALI-019"}]})[1]["result"]
        self.assertEqual(r["matches"], [])                         # a different code is not the same medicine
        self.assertIn("MED-ASALI-009", r["near_misses"][0]["one_edit_away"])


class Coordination(unittest.TestCase):

    def test_routing(self):
        from integration.federation.coordinator import route, unfold
        from integration.federation.query_parser import parse
        self.assertEqual(route(parse("was the cold chain of MED-ASALI-009 maintained"))["databases"], ["db2", "db3"])
        self.assertEqual(route(parse("any complaints about Novamox in Mumbai"))["databases"], ["db4"])
        self.assertEqual(route(parse("is MED-ASALI-009 genuine"))["databases"], list(DBS))
        pq = parse("Which shipments did DIST-004 send to VND-012?")
        self.assertNotIn("ments", pq.terms)
        plan = unfold(pq, route(pq)["databases"], "T")
        combined = [s for s in plan["db2"] if s["target"] == "distribution_batches"]
        self.assertEqual(len(combined), 1)
        self.assertEqual({w["field"] for w in combined[0]["where"]}, {"distributor_id", "destination_vendor_id"})

    def test_end_to_end_with_provenance(self):
        from integration.federation.coordinator import federated_query
        res = federated_query("Is MED-ASALI-009 genuine and was its cold chain maintained?")
        self.assertEqual(res["source_status"], {d: "ok" for d in DBS})
        self.assertFalse(res["partial"])
        for d in DBS:
            self.assertEqual(res["sources"][d]["served_by"]["pid"], PROCS[d].pid)
            self.assertTrue(all(sq["database"] == d for sq in res["sources"][d]["subqueries"]))
        v = res["verdicts"][0]
        self.assertEqual((v["status"], v["verdict"], v["trust_score"]), ("COMPUTED", "SUSPICIOUS", 65))
        self.assertEqual(res["combined"]["medicines"][0]["item_code"], "MED-ASALI-009")

    def test_verdicts_over_the_network_equal_local_verdicts(self):
        script = ("import json,sys,io,contextlib;sys.path.insert(0,sys.argv[1]);from api.verify_item import verify\n"
                  "out={}\n"
                  "for c in json.loads(sys.argv[2]):\n"
                  "    with contextlib.redirect_stdout(io.StringIO()): r=verify(c,silent=True)\n"
                  "    out[c]=[r['verdict'],r['trust_score'],sorted(r['veto_codes']),r['lifecycle_state'],r['db_coverage']]\n"
                  "print(json.dumps(out))")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ASALI_")}
        env.update({"ASALI_DB_DIR": os.path.join(FULL_DIR, "databases"), "ASALI_DB4_REST_URL": "offline",
                    "ASALI_NOSQL_FILE": os.path.join(FULL_DIR, "nosql_store", "db1_retail_pos.json"),
                    "PYTHONIOENCODING": "utf-8"})
        p = subprocess.run([PY, "-c", script, BASE, json.dumps(CURATED)], env=env, cwd=BASE,
                           capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        local = json.loads(p.stdout.strip().splitlines()[-1])
        from api.verify_item import verify
        import contextlib, io
        for c in CURATED:
            with contextlib.redirect_stdout(io.StringIO()):
                r = verify(c, silent=True)
            with self.subTest(code=c):
                self.assertEqual([r["verdict"], r["trust_score"], sorted(r["veto_codes"]), r["lifecycle_state"],
                                  r["db_coverage"]], local[c])
                self.assertEqual(r["federation_mode"], "remote")

    def test_unreachable_database_gives_partial_result_and_no_verdict(self):
        from integration.federation.coordinator import federated_query
        saved = os.environ["ASALI_DB4_URL"]
        os.environ["ASALI_DB4_URL"] = f"http://127.0.0.1:{free_port()}"      # nothing listens there
        try:
            res = federated_query("Is MED-ASALI-001 genuine?")
        finally:
            os.environ["ASALI_DB4_URL"] = saved
        self.assertEqual(res["source_status"]["db4"], "unreachable")
        self.assertTrue(all(res["source_status"][d] == "ok" for d in ("db1", "db2", "db3")))
        self.assertTrue(res["partial"])
        self.assertTrue(res["sources"]["db3"]["subqueries"][0]["matches"])  # the others still answered
        self.assertEqual(res["verdicts"][0]["status"], "WITHHELD")

    def test_slow_database_times_out(self):
        from integration.federation.coordinator import federated_query
        saved = os.environ["ASALI_DB4_URL"], os.environ["ASALI_NODE_TIMEOUT_SEC"]
        os.environ["ASALI_DB4_URL"] = url("slow_db4")
        os.environ["ASALI_NODE_TIMEOUT_SEC"] = "1"
        try:
            t0 = time.time()
            res = federated_query("Any complaints about MED-NAKALI-001?", verify=False)
            elapsed = time.time() - t0
        finally:
            os.environ["ASALI_DB4_URL"], os.environ["ASALI_NODE_TIMEOUT_SEC"] = saved
        self.assertEqual(res["source_status"]["db4"], "timeout")
        self.assertLess(elapsed, 6)          # gave up after the first subquery, did not wait on all five

    def test_coordinator_created_no_database_files(self):
        from integration.federation.coordinator import federated_query
        federated_query("verify MED-NAKALI-001")          # a NAKALI verdict: Phase 1 would file a complaint
        made = {f for f in os.listdir(STATE_DIR)}
        self.assertFalse({f for f in made if f.startswith(("db1_", "db2_", "db3_", "db4_"))}, made)
        self.assertFalse(os.path.exists(os.path.join(BASE, "integration", "databases")))


if __name__ == "__main__":
    unittest.main()
