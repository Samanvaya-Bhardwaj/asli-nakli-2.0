#!/usr/bin/env python3
"""
coordinator_service.py
----------------------
The Phase 3 federated query coordinator (Machine 1). It holds no database: it
plans each question, sends subqueries to the four database services, and
combines what they return.

    python api/coordinator_service.py --env-file deploy/local.env

Endpoints:
  GET  /health                       coordinator identity
  GET  /api/v3/federation/nodes      every database service: address, machine, status,
                                     and whether this is a local simulation or multi-machine
  POST /api/v3/federated/plan        {"query": "..."}  understanding, routing, subqueries (nothing sent)
  POST /api/v3/federated/query       {"query": "...", "max_hops": 2, "verify": true}
If ASALI_COORDINATOR_TOKEN is set, the /api/v3 endpoints require it as a bearer token.
"""

from __future__ import annotations
import argparse
import hmac
import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def build(env_file):
    from integration.federation import runtime
    runtime.bootstrap(env_file)
    # Must be set before anything imports integration.resolver: from here on the GAV
    # resolver, entity resolver and verifier reach DB1-DB4 over HTTP only.
    os.environ["ASALI_FEDERATION"] = "remote"
    runtime.all_nodes()                     # fail fast on missing configuration
    from integration.federation import coordinator
    from integration.federation.query_parser import parse
    return runtime, coordinator, parse


def make_handler(coordinator, parse, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AsaliCoordinator/3.0"

        def log_message(self, fmt, *args):
            if os.environ.get("ASALI_NODE_LOG"):
                sys.stderr.write(f"[coordinator] {self.address_string()} {fmt % args}\n")

        def _send(self, status, body):
            raw = json.dumps(body, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self):
            if not token:
                return True
            got = self.headers.get("Authorization", "")
            if got.startswith("Bearer ") and hmac.compare_digest(got[7:].strip().encode(), token.encode()):
                return True
            self._send(401, {"error": "missing or wrong bearer token"})
            return False

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                return self._send(200, {"status": "online", "role": "federated query coordinator",
                                        "hostname": socket.gethostname(),
                                        "machine_label": os.environ.get("ASALI_MACHINE_LABEL") or "unlabelled",
                                        "holds_databases": []})
            if not self._authorised():
                return
            if path == "/api/v3/federation/nodes":
                return self._send(200, coordinator.nodes_status())
            self._send(404, {"error": "no such endpoint"})

        def do_POST(self):
            path = urlparse(self.path).path
            if not self._authorised():
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self._send(400, {"error": "body is not valid JSON"})
            text = str(body.get("query") or "").strip()
            if not text:
                return self._send(400, {"error": "query is required"})
            try:
                if path == "/api/v3/federated/plan":
                    pq = parse(text)
                    routing = coordinator.route(pq)
                    return self._send(200, {"question": text, "understanding": pq.__dict__, "routing": routing,
                                            "subqueries": coordinator.unfold(pq, routing["databases"], "PLAN",
                                                                             int(body.get("max_hops", 2)))})
                if path == "/api/v3/federated/query":
                    return self._send(200, coordinator.federated_query(
                        text, max_hops=max(0, min(int(body.get("max_hops", 2)), 3)),
                        verify=bool(body.get("verify", True)),
                        method="bfs" if body.get("method") == "bfs" else "score",
                        max_augmentation=body.get("max_augmentation"), top_n=body.get("top_n"),
                        documents=bool(body.get("documents", True))))
            except Exception as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
            self._send(404, {"error": "no such endpoint"})

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 3 federated query coordinator")
    ap.add_argument("--env-file")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)
    try:
        runtime, coordinator, parse = build(args.env_file)
    except Exception as e:
        print(f"[coordinator] configuration error: {e}", file=sys.stderr)
        return 2
    host, port = runtime.coordinator_bind()
    host, port = args.host or host, args.port or port
    if not port:
        print("[coordinator] set ASALI_COORDINATOR_PORT or pass --port", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((host, port), make_handler(coordinator, parse,
                                                            os.environ.get("ASALI_COORDINATOR_TOKEN", "").strip()))
    print(f"[coordinator] listening on http://{host}:{port}; databases: "
          + ", ".join(f"{d}={c.url}" for d, c in runtime.all_nodes().items()), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
