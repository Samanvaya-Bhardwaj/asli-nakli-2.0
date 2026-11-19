"""Build each organisation's store, read-write and read-only, against a fresh database.

SQLite uses a temp file. PostgreSQL and MongoDB come from ports 55432 and 57017 (infra/compose/test-engines.yml,
or infra/scripts/local_engines.py when Docker is not available). If a port is closed, those tests are skipped
with the reason; they are never silently passed.
"""

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from asali_node.stores.registry import ORG_STORES, OrgStore, store_class

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
_TMP_ENGINES = Path(os.environ.get("TEMP", "/tmp")) / "asali-engines"


def _find(name: str, env: str, exe: str) -> None:
    """Point at vendor zip builds if the usual environment variable is not set (Windows, no Docker)."""
    if os.environ.get(env):
        return
    for p in _TMP_ENGINES.rglob(exe) if _TMP_ENGINES.exists() else []:
        os.environ[env] = str(p.parent)
        return


_find("pg", "ASALI_PG_BIN", "postgres.exe")
_find("mongo", "ASALI_MONGO_BIN", "mongod.exe")
if os.environ.get("ASALI_PG_BIN"):  # lets psycopg find libpq when its bundled copy is blocked
    os.environ["PATH"] = os.environ["ASALI_PG_BIN"] + os.pathsep + os.environ["PATH"]

import local_engines as le  # noqa: E402


@pytest.fixture(scope="session")
def engines_up() -> dict[str, bool]:
    pg_dir, mongo_dir = le.engines_from_env()
    try:
        if pg_dir:
            le.start_postgres(pg_dir)
        if mongo_dir:
            le.start_mongo(mongo_dir)
    except Exception as e:  # noqa: BLE001 - a failed start only means those tests skip, with the reason
        print("could not start local engines:", e)
    return {"pg": le.port_open(le.PG_PORT), "mongo": le.port_open(le.MONGO_PORT)}


@dataclass
class Env:
    spec: OrgStore
    rw_target: str
    ro_target: str
    city: str = "Test City"

    def rw(self) -> Any:
        s = store_class(self.spec.org_id)(self.rw_target, "rw", self.city)
        s.init_schema()
        return s

    def ro(self) -> Any:
        return store_class(self.spec.org_id)(self.ro_target, "ro", self.city)


def _db_name(org_id: str) -> str:
    return "asali_" + org_id.replace("-", "_")


def _pg_env(spec: OrgStore) -> Env:
    import psycopg

    name = _db_name(spec.org_id)
    with psycopg.connect(le.PG_SUPER, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{name}" OWNER app_rw')
        c.execute(f'GRANT CONNECT ON DATABASE "{name}" TO share_ro')
    base = f"postgresql://%s:%s@127.0.0.1:{le.PG_PORT}/{name}"
    with psycopg.connect(le.PG_SUPER.replace("/postgres", f"/{name}"), autocommit=True) as c:
        c.execute("GRANT USAGE ON SCHEMA public TO share_ro")
        c.execute("ALTER DEFAULT PRIVILEGES FOR ROLE app_rw IN SCHEMA public GRANT SELECT ON TABLES TO share_ro")
        c.execute("ALTER DEFAULT PRIVILEGES FOR ROLE app_rw IN SCHEMA public GRANT SELECT ON SEQUENCES TO share_ro")
    return Env(spec, base % ("app_rw", le.RW_PW), base % ("share_ro", le.RO_PW))


def _mongo_env(spec: OrgStore) -> Env:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure

    name = _db_name(spec.org_id)
    admin: MongoClient[Any] = MongoClient(le.MONGO_ADMIN)
    admin.drop_database(name)
    for user, pw, role in (("app_rw", le.RW_PW, "readWrite"), ("share_ro", le.RO_PW, "read")):
        try:
            admin[name].command("createUser", user, pwd=pw, roles=[role])
        except OperationFailure as e:
            if e.code != 51003:  # the user already exists from an earlier run
                raise
    base = f"mongodb://%s:%s@127.0.0.1:{le.MONGO_PORT}/{name}?authSource={name}"
    return Env(spec, base % ("app_rw", le.RW_PW), base % ("share_ro", le.RO_PW))


@pytest.fixture(params=list(ORG_STORES), ids=list(ORG_STORES))
def env(request: pytest.FixtureRequest, tmp_path: Path, engines_up: dict[str, bool]) -> Env:
    spec = ORG_STORES[request.param]
    if importlib.util.find_spec(f"asali_node.stores.{spec.module}") is None:
        pytest.skip(f"{spec.org_id}: store not written yet")
    if spec.engine == "sqlite":
        path = str(tmp_path / f"{spec.org_id}.sqlite")
        return Env(spec, path, path)
    if not engines_up[spec.engine]:
        pytest.skip(f"{spec.org_id}: {spec.engine} is not reachable (start test-engines.yml or local_engines.py)")
    return _pg_env(spec) if spec.engine == "pg" else _mongo_env(spec)


def of_kind(*kinds: str) -> Any:
    """Decorator-free helper: skip a test unless the org is one of the kinds."""

    def check(env: Env) -> None:
        if env.spec.kind not in kinds:
            pytest.skip(f"{env.spec.org_id} is a {env.spec.kind}")

    return check
