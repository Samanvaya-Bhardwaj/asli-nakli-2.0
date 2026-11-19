"""Build each organisation's store, read-write and read-only, against a fresh database.

SQLite uses a temp file. PostgreSQL and MongoDB come from ports 55432 and 57017 (infra/compose/test-engines.yml,
or infra/scripts/local_engines.py when Docker is not available). If a port is closed, those tests are skipped
with the reason; they are never silently passed.
"""

import contextlib
import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
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
    except Exception as e:
        print("could not start local engines:", e)
    return {"pg": le.port_open(le.PG_PORT), "mongo": le.port_open(le.MONGO_PORT)}


@dataclass
class Env:
    spec: OrgStore
    rw_target: str
    ro_target: str
    city: str = "Test City"
    opened: list[Any] = field(default_factory=list)

    def rw(self) -> Any:
        s = store_class(self.spec.org_id)(self.rw_target, "rw", self.city)
        s.init_schema()
        self.opened.append(s)
        return s

    def ro(self) -> Any:
        s = store_class(self.spec.org_id)(self.ro_target, "ro", self.city)
        self.opened.append(s)
        return s


def _db_name(org_id: str) -> str:
    return "asali_" + org_id.replace("-", "_")


def _pg_env(spec: OrgStore) -> Env:
    import psycopg

    name = _db_name(spec.org_id)
    with psycopg.connect(le.PG_SUPER, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}" OWNER app_rw')
            c.execute(f'GRANT CONNECT ON DATABASE "{name}" TO share_ro')
    base = f"postgresql://%s:%s@127.0.0.1:{le.PG_PORT}/{name}"
    with psycopg.connect(f"{le.PG_SUPER.rsplit('/', 1)[0]}/{name}", autocommit=True) as c:
        # a fresh, empty schema for every test, with the same grants the compose init script sets
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public AUTHORIZATION app_rw")
        c.execute("GRANT USAGE ON SCHEMA public TO share_ro")
        c.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE app_rw IN SCHEMA public GRANT SELECT ON TABLES TO share_ro"
        )
        c.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE app_rw IN SCHEMA public GRANT SELECT ON SEQUENCES TO share_ro"
        )
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


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Run each test once per organisation of the kinds the module names in KINDS (all kinds if it has none)."""
    if "env" in metafunc.fixturenames:
        kinds = getattr(metafunc.module, "KINDS", None)
        ids = [o for o, s in ORG_STORES.items() if kinds is None or s.kind in kinds]
        metafunc.parametrize("env", ids, indirect=True)


@pytest.fixture
def env(request: pytest.FixtureRequest, tmp_path: Path, engines_up: dict[str, bool]) -> Iterator[Env]:
    spec = ORG_STORES[request.param]
    if spec.engine == "sqlite":
        path = str(tmp_path / f"{spec.org_id}.sqlite")
        e = Env(spec, path, path)
    else:
        if not engines_up[spec.engine]:
            pytest.skip(
                f"{spec.org_id}: {spec.engine} is not reachable (start test-engines.yml or local_engines.py)"
            )
        e = _pg_env(spec) if spec.engine == "pg" else _mongo_env(spec)
    yield e
    for s in e.opened:  # close every pool or connection the test opened
        with contextlib.suppress(Exception):
            s.close()
