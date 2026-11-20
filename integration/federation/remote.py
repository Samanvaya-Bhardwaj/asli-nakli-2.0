"""
remote.py
---------
How the coordinator talks to the database services.

  NodeClient           HTTP + bearer token + timeout to one database service;
                       every failure is classified (timeout / unreachable /
                       auth_failed / refused / error), never swallowed silently
  RemoteSourceWrapper  a Phase 1 BaseWrapper whose query() runs on the
                       database's own machine (/api/v3/legacy/lookup), so the
                       existing GAV resolver, canonical model and verifier work
                       unchanged over the network
  collect_status()     records which services answered during a block of code,
                       so a verdict is never issued on a silently missing source

DB4's REST envelope {"meta", "data"} is unwrapped here: that heterogeneity is
the wrapper's job, as in Phase 1.
"""

from __future__ import annotations
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Dict, Optional

from integration.federation import runtime
from integration.wrappers.base_wrapper import BaseWrapper, SourceMetadata

_local = threading.local()


class NodeError(RuntimeError):
    def __init__(self, db_id: str, status: str, message: str):
        super().__init__(f"{db_id}: {status}: {message}")
        self.db_id, self.status, self.message = db_id, status, message


@contextmanager
def collect_status():
    """Within the block, every call to a database service is recorded: db -> status."""
    prev = getattr(_local, "log", None)
    _local.log = {}
    try:
        yield _local.log
    finally:
        _local.log = prev


def _record(db_id: str, status: str):
    log = getattr(_local, "log", None)
    if log is not None and log.get(db_id) in (None, "ok"):
        log[db_id] = status


class NodeClient:
    def __init__(self, cfg: runtime.NodeConfig):
        self.cfg = cfg

    def request(self, method: str, path: str, body: Optional[dict] = None, auth: bool = True,
                timeout: Optional[float] = None) -> Dict[str, Any]:
        url = self.cfg.url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json", "User-Agent": "AsaliFederatedCoordinator/3.0"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = f"Bearer {self.cfg.token}"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.cfg.timeout) as r:
                payload = json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", "")
            except Exception:
                detail = ""
            status = "auth_failed" if e.code == 401 else ("refused" if e.code == 400 else "error")
            _record(self.cfg.db_id, status)
            raise NodeError(self.cfg.db_id, status, f"HTTP {e.code} {detail}".strip())
        except (socket.timeout, TimeoutError) as e:
            _record(self.cfg.db_id, "timeout")
            raise NodeError(self.cfg.db_id, "timeout", f"no answer within {timeout or self.cfg.timeout:.1f}s")
        except urllib.error.URLError as e:
            reason = e.reason
            status = "timeout" if isinstance(reason, (socket.timeout, TimeoutError)) else "unreachable"
            _record(self.cfg.db_id, status)
            raise NodeError(self.cfg.db_id, status, str(reason))
        except (ConnectionError, OSError) as e:
            _record(self.cfg.db_id, "unreachable")
            raise NodeError(self.cfg.db_id, "unreachable", str(e))
        _record(self.cfg.db_id, "ok")
        if self.cfg.db_id == "db4" and isinstance(payload, dict) and "data" in payload and "meta" in payload:
            payload = payload["data"]          # DB4's REST envelope
        if isinstance(payload, dict):
            payload["_elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return payload

    def health(self) -> Dict[str, Any]:
        return self.request("GET", "/health", auth=False, timeout=min(self.cfg.timeout, 2.5))


def client(db_id: str) -> NodeClient:
    return NodeClient(runtime.node_config(db_id))


# -- Phase 1 wrapper contract over the network ----------------------------------------

_LEGACY = {
    "db1": ("db1_purchase", "Retail Pharmacy POS Network", "NoSQL Document Store", "scan_code"),
    "db2": ("db2_distributor", "Distributor Logistics ERP", "Relational SQL Database", "batch_serial"),
    "db3": ("db3_manufacturer", "CDSCO Manufacturer Master Registry", "Relational SQL Database", "product_uid"),
    "db4": ("db4_ministry", "Ministry of Consumer Affairs & CDSCO (INGRAM)", "HTTP RESTful Web Service",
            "complaint_item_ref"),
}


class RemoteSourceWrapper(BaseWrapper):
    """The same wrapper contract as Phase 1; the query itself runs on the database's machine."""

    def __init__(self, db_id: str):
        sid, *_ = _LEGACY[db_id]
        super().__init__(sid)
        self.db_id = db_id

    def get_metadata(self) -> SourceMetadata:
        sid, name, kind, key = _LEGACY[self.db_id]
        try:
            cfg = runtime.node_config(self.db_id)
            online = self.health_check()
            where = cfg.url
        except runtime.ConfigError:
            online, where = False, "not configured"
        return SourceMetadata(source_id=sid, source_name=f"{name} @ {where}", source_type=kind,
                              paradigm=runtime.DB_PARADIGMS[self.db_id], protocol="HTTP/1.1 JSON, bearer token",
                              native_key=key, status="ONLINE" if online else "UNREACHABLE")

    def health_check(self) -> bool:
        try:
            return client(self.db_id).health().get("status") == "online"
        except (NodeError, runtime.ConfigError):
            return False

    def query(self, canonical_key: str, native_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            res = client(self.db_id).request("POST", "/api/v3/legacy/lookup", {"key": canonical_key})
            out = dict(res.get("result") or {})
            out["served_by"] = res.get("source")
            out["remote_elapsed_ms"] = res.get("_elapsed_ms")
            return out
        except (NodeError, runtime.ConfigError) as e:
            status = getattr(e, "status", "not_configured")
            _record(self.db_id, status)
            return {"source_id": self.source_id, "found": False, "source_unavailable": True,
                    "unavailable_reason": f"{status}: {getattr(e, 'message', str(e))}",
                    "native_query": f"POST /api/v3/legacy/lookup key={canonical_key} (failed: {status})",
                    "paradigm": runtime.DB_PARADIGMS[self.db_id]}


def remote_catalog(db_id: str):
    """Rows the Phase 1 entity resolver reads from DB3 / DB2, fetched from their services."""
    return client(db_id).request("GET", "/api/v3/legacy/catalog").get("rows", [])


_version_cache: Dict[str, tuple] = {}


def data_version(db_id: str, max_age: float = 2.0) -> int:
    now = time.monotonic()
    hit = _version_cache.get(db_id)
    if hit and now - hit[1] < max_age:
        return hit[0]
    try:
        v = int(client(db_id).health().get("data_version") or 0)
    except (NodeError, runtime.ConfigError):
        v = 0
    _version_cache[db_id] = (v, now)
    return v
