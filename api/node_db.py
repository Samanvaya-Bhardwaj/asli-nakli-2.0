#!/usr/bin/env python3
"""
node_db.py
----------
One Phase 3 database service. Start one per database, on the machine that holds it:

    python api/node_db.py --db db3 --env-file deploy/machine2.env

It opens ONLY its own database (DB1 also its JSON document collections). With
ASALI_STRICT_ISOLATION=1 (the default) it refuses to start if it can see another
database's file in its data directory, so a "distributed" run cannot quietly be
reading a full local copy.

Endpoints (all JSON; everything except /health needs  Authorization: Bearer <ASALI_DBN_TOKEN>):
  GET  /health                     identity, machine, data version; no data, no token
  GET  /api/v3/schema              tables / collections, keys, FK-PK relationships
  POST /api/v3/subquery            {"subquery": {...}}  execute locally (+ local context discovery)
  POST /api/v3/context/discover    {"subquery": {...}}  context only, seeded by the subquery's matches
  POST /api/v3/legacy/lookup       {"key": "MED-..."}   the Phase 1 wrapper result, computed here
  GET  /api/v3/legacy/catalog      rows the Phase 1 entity resolver needs (DB2, DB3)
  GET  /api/v3/documents/stats     this source's document store (ASALI_DOCS_DIR): ingestion statistics
  POST /api/v3/documents/search    context-aware search of this source's documents (doc_store.py)
DB4 only, kept from Phase 1 (same bearer token as v3):
  GET  /api/v1/health, /api/v1/complaints|blacklist|lab_reports|alerts?item_ref=

DB4 answers in the REST envelope it always used, {"meta": {...}, "data": {...}};
the other three answer with the object itself.
"""

from __future__ import annotations
import argparse
import hmac
import json
import os
import platform
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from integration.federation import runtime  # noqa: E402

FOREIGN_FILES = {
    "db1": "db1_purchase_registry.sqlite", "db2": "db2_distributor_ledger.sqlite",
    "db3": "db3_manufacturer_registry.sqlite", "db4": "db4_ministry_reports.sqlite",
}


def isolation_problems(db_id: str) -> list:
    """Files this service can see that belong to another database."""
    from integration.uncertainty import paths
    problems = []
    for other, fname in FOREIGN_FILES.items():
        if other != db_id and os.path.exists(os.path.join(paths.db_dir(), fname)):
            problems.append(os.path.join(paths.db_dir(), fname))
    if db_id != "db1":
        scan = paths.nosql_file()
        if os.path.exists(scan):
            problems.append(scan)
    return problems


def make_handler(db_id: str, token: str, started: float):
    from integration.federation.local_engine import NodeEngine, SubqueryError
    from integration.uncertainty import paths
    engine = NodeEngine(db_id)
    delay = float(os.environ.get("ASALI_NODE_DELAY_SEC") or 0)   # for timeout tests only
    machine = os.environ.get("ASALI_MACHINE_LABEL") or "unlabelled"
    physical = os.environ.get("ASALI_PHYSICAL_HOST") or socket.gethostname()

    class Handler(BaseHTTPRequestHandler):
        server_version = f"AsaliNode/{db_id}"

        def log_message(self, fmt, *args):
            if os.environ.get("ASALI_NODE_LOG"):
                sys.stderr.write(f"[{db_id}] {self.address_string()} {fmt % args}\n")

        def _identity(self) -> dict:
            return {"database": db_id, "name": runtime.DB_NAMES[db_id], "paradigm": runtime.DB_PARADIGMS[db_id],
                    "machine_label": machine, "physical_host": physical, "os_hostname": socket.gethostname(),
                    "in_container": os.path.exists("/.dockerenv"), "platform": platform.platform(),
                    "pid": os.getpid(), "listening_on": f"{self.server.server_address[0]}:{self.server.server_address[1]}",
                    "seen_client": self.client_address[0]}

        def _send(self, status: int, body, envelope: bool = True):
            if db_id == "db4" and envelope and status < 400:
                body = {"meta": {"service": "DB4 Ministry Reports (federated REST node)", "status": status,
                                 "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, "data": body}
            raw = json.dumps(body, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self) -> bool:
            got = self.headers.get("Authorization", "")
            ok = got.startswith("Bearer ") and hmac.compare_digest(got[7:].strip().encode(), token.encode())
            if not ok:
                self._send(401, {"error": "missing or wrong bearer token", "database": db_id}, envelope=False)
            return ok

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8"))
            except ValueError:
                raise SubqueryError("request body is not valid JSON")

        def do_OPTIONS(self):
            self._send(204, {}, envelope=False)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/health", "/api/v3/health"):
                files = engine.data_files()
                return self._send(200, {"status": "online", **self._identity(),
                                        "data_version": engine.data_version(),
                                        "data_files": [{"file": os.path.basename(p), "present": os.path.exists(p)}
                                                       for p in files],
                                        "isolation": {"strict": os.environ.get("ASALI_STRICT_ISOLATION", "1") != "0",
                                                      "foreign_files_visible": len(isolation_problems(db_id))},
                                        "uptime_sec": round(time.time() - started, 1)}, envelope=False)
            if not self._authorised():
                return
            time.sleep(delay)
            try:
                if url.path == "/api/v3/schema":
                    return self._send(200, {"source": self._identity(), "schema": engine.schema()})
                if url.path == "/api/v3/legacy/catalog":
                    return self._send(200, {"source": self._identity(), "rows": engine.legacy_catalog()})
                if url.path == "/api/v3/documents/stats":
                    from integration.federation.doc_store import store
                    return self._send(200, {"source": self._identity(), "stats": store(db_id).stats()})
                if db_id == "db4" and url.path.startswith("/api/v1/"):
                    return self._legacy_v1(url)
                return self._send(404, {"error": "no such endpoint", "path": url.path}, envelope=False)
            except Exception as e:   # never leak a stack trace, but say what failed
                return self._send(500, {"error": f"{type(e).__name__}: {e}", "database": db_id}, envelope=False)

        def _legacy_v1(self, url):
            from api.ministry_service import MinistryDataStore
            store = MinistryDataStore(paths.db_path("db4"))
            ref = parse_qs(url.query).get("item_ref", [None])[0]
            fn = {"/api/v1/complaints": store.get_complaints, "/api/v1/blacklist": store.get_blacklist,
                  "/api/v1/lab_reports": store.get_lab_reports, "/api/v1/alerts": store.get_alerts}.get(url.path)
            if url.path == "/api/v1/health":
                return self._send(200, {"status": "online", "service": "DB4 federated node"}, envelope=False)
            if fn is None:
                return self._send(404, {"error": "no such endpoint"}, envelope=False)
            rows = fn(ref)
            return self._send(200, {"meta": {"query_param": {"item_ref": ref}, "count": len(rows)}, "data": rows},
                              envelope=False)

        def do_POST(self):
            url = urlparse(self.path)
            if not self._authorised():
                return
            time.sleep(delay)
            try:
                body = self._body()
                if url.path in ("/api/v3/subquery", "/api/v3/context/discover"):
                    res = engine.run(body.get("subquery") or {}, discover_context=True)
                    if url.path.endswith("/discover"):
                        res = {k: res[k] for k in ("subquery_id", "database", "context", "context_summary",
                                                   "bridge_keys", "local_queries_executed", "timing_ms")}
                    return self._send(200, {"source": self._identity(), "result": res})
                if url.path == "/api/v3/documents/search":
                    # this source's own documents, searched with the coordinator's context-aware request
                    from integration.federation.doc_store import store
                    return self._send(200, {"source": self._identity(), "result": store(db_id).search(body)})
                if url.path == "/api/v3/legacy/lookup":
                    key = str(body.get("key") or "").strip()
                    if not key:
                        raise SubqueryError("key is required")
                    return self._send(200, {"source": self._identity(), "result": engine.legacy_lookup(key)})
                return self._send(404, {"error": "no such endpoint", "path": url.path}, envelope=False)
            except SubqueryError as e:
                return self._send(400, {"error": str(e), "database": db_id}, envelope=False)
            except Exception as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}", "database": db_id}, envelope=False)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 3 database service (one per database)")
    ap.add_argument("--db", required=True, choices=list(runtime.DB_IDS))
    ap.add_argument("--env-file", help="KEY=VALUE file, e.g. deploy/local.env")
    ap.add_argument("--host", help="interface to bind (default ASALI_NODE_BIND)")
    ap.add_argument("--port", type=int, help="port (default from ASALI_DBN_PORT or ASALI_DBN_URL)")
    args = ap.parse_args(argv)
    try:
        runtime.bootstrap(args.env_file)
        host, port = runtime.node_bind(args.db, args.port)
    except runtime.ConfigError as e:
        print(f"[{args.db}] configuration error: {e}", file=sys.stderr)
        return 2
    host = args.host or host
    token = os.environ.get(f"ASALI_{args.db.upper()}_TOKEN", "").strip()
    if not token:
        print(f"[{args.db}] refusing to start: ASALI_{args.db.upper()}_TOKEN is not set", file=sys.stderr)
        return 2

    from integration.uncertainty import paths
    own = [p for p in ([paths.db_path(args.db)] + ([paths.nosql_file()] if args.db == "db1" else []))]
    missing = [p for p in own if not os.path.exists(p)]
    if missing:
        print(f"[{args.db}] refusing to start: data not found: {missing}", file=sys.stderr)
        return 2
    foreign = isolation_problems(args.db)
    if foreign and os.environ.get("ASALI_STRICT_ISOLATION", "1") != "0":
        print(f"[{args.db}] refusing to start: this service would be able to read other databases: {foreign}. "
              f"Give it a data directory holding only its own database (scripts/prepare_node_data.py), "
              f"or set ASALI_STRICT_ISOLATION=0 for development.", file=sys.stderr)
        return 3

    server = ThreadingHTTPServer((host, port), make_handler(args.db, token, time.time()))
    print(f"[{args.db}] {runtime.DB_NAMES[args.db]} listening on http://{host}:{port}  "
          f"machine={os.environ.get('ASALI_MACHINE_LABEL') or 'unlabelled'}  data={paths.db_dir()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
