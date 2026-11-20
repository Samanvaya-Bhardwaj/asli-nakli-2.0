"""
runtime.py
----------
Where the four database services are, and how to reach them. Nothing here is
hard-coded: every address, port, token and timeout comes from the environment,
usually through an env file passed with --env-file (or ASALI_ENV_FILE):

  deploy/local.env                 all four services on this machine (simulation)
  deploy/machine1.env.example      Machine 1: DB1, DB2 and the coordinator
  deploy/machine2.env.example      Machine 2: DB3 and DB4

Per database N (1-4):
  ASALI_DBN_URL       base URL the coordinator uses, e.g. http://192.168.1.20:8023
  ASALI_DBN_TOKEN     bearer token that database's service requires
  ASALI_DBN_MACHINE   label of the machine it runs on (reporting only)
Service side:
  ASALI_NODE_BIND     interface a database service listens on (0.0.0.0 for the LAN)
  ASALI_MACHINE_LABEL label this machine reports in /health
Coordinator:
  ASALI_COORDINATOR_BIND, ASALI_COORDINATOR_PORT, ASALI_NODE_TIMEOUT_SEC
Mode:
  ASALI_FEDERATION=remote   the GAV resolver and verifier reach DB1-DB4 over HTTP
                            instead of opening local files (Phase 1/2 default: local)
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse

DB_IDS = ("db1", "db2", "db3", "db4")
DB_NAMES = {
    "db1": "Retail POS",
    "db2": "Distributor ERP",
    "db3": "Manufacturer Registry",
    "db4": "Ministry Reports",
}
DB_PARADIGMS = {
    "db1": "Document store (JSON collections; SQLite authoritative for writes)",
    "db2": "Relational (SQLite)",
    "db3": "Relational (SQLite)",
    "db4": "REST microservice over SQLite",
}


class ConfigError(RuntimeError):
    pass


def load_env_file(path: Optional[str]) -> Dict[str, str]:
    """KEY=VALUE lines; '#' comments; existing environment variables win."""
    loaded = {}
    if not path:
        return loaded
    if not os.path.exists(path):
        raise ConfigError(f"env file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    return loaded


def bootstrap(env_file: Optional[str] = None) -> None:
    load_env_file(env_file or os.environ.get("ASALI_ENV_FILE"))


def remote_mode() -> bool:
    return os.environ.get("ASALI_FEDERATION", "local").strip().lower() == "remote"


@dataclass
class NodeConfig:
    db_id: str
    url: str
    token: str
    machine: str
    timeout: float

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or ""

    @property
    def port(self) -> int:
        return urlparse(self.url).port or 80


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def node_config(db_id: str, required: bool = True) -> Optional[NodeConfig]:
    key = db_id.upper()
    url = _env(f"ASALI_{key}_URL").rstrip("/")
    token = _env(f"ASALI_{key}_TOKEN")
    if not url or not token:
        if required:
            raise ConfigError(f"ASALI_{key}_URL and ASALI_{key}_TOKEN must be set "
                              f"(for one machine: --env-file deploy/local.env)")
        return None
    return NodeConfig(db_id, url, token, _env(f"ASALI_{key}_MACHINE") or "unlabelled",
                      float(_env("ASALI_NODE_TIMEOUT_SEC") or 4.0))


def all_nodes(required: bool = True) -> Dict[str, NodeConfig]:
    out = {}
    for d in DB_IDS:
        cfg = node_config(d, required=required)
        if cfg:
            out[d] = cfg
    return out


def node_bind(db_id: str, port: Optional[int] = None) -> tuple:
    """(host, port) a database service listens on."""
    host = _env("ASALI_NODE_BIND") or "127.0.0.1"
    if port is None:
        cfg = node_config(db_id, required=False)
        port_env = _env(f"ASALI_{db_id.upper()}_PORT")
        if port_env:
            port = int(port_env)
        elif cfg:
            port = cfg.port
        else:
            raise ConfigError(f"no port for {db_id}: set ASALI_{db_id.upper()}_PORT or ASALI_{db_id.upper()}_URL")
    return host, int(port)


def coordinator_bind() -> tuple:
    return _env("ASALI_COORDINATOR_BIND") or "127.0.0.1", int(_env("ASALI_COORDINATOR_PORT") or 0)
