"""Start a real PostgreSQL 16 and MongoDB 7 without Docker, for tests on a PC that cannot run it.

    python infra/scripts/local_engines.py start      # prints the two ports and leaves them running
    python infra/scripts/local_engines.py stop

Needs the vendors' own zip builds unpacked somewhere (set ASALI_PG_BIN to the folder holding
postgres.exe and ASALI_MONGO_BIN to the folder holding mongod.exe). Same roles as the compose
init templates: app_rw (owner) and share_ro (read only). Data goes to a temp folder.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PG_PORT, MONGO_PORT = 55432, 57017
PG_SUPER = f"postgresql://postgres@127.0.0.1:{PG_PORT}/postgres"
MONGO_ADMIN = f"mongodb://admin:admin_pw@127.0.0.1:{MONGO_PORT}/admin?authSource=admin"
RW_PW, RO_PW = "app_rw_pw", "share_ro_pw"
WORK = Path(tempfile.gettempdir()) / "asali-test-engines"


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)  # type: ignore[call-overload]


def start_postgres(bin_dir: Path) -> None:
    if port_open(PG_PORT):
        return
    data = WORK / "pg"
    if not (data / "PG_VERSION").exists():
        data.parent.mkdir(parents=True, exist_ok=True)
        r = _run([str(bin_dir / "initdb.exe"), "-D", str(data), "-U", "postgres", "-A", "trust",
                  "--encoding=UTF8", "--locale=C"])  # fmt: skip
        if r.returncode:
            raise RuntimeError(r.stderr)
    # pg_ctl's child keeps inherited pipes open, so send its output to a file instead of capturing it
    r = subprocess.run(
        [str(bin_dir / "pg_ctl.exe"), "start", "-D", str(data), "-w", "-l", str(WORK / "pg.log"),
         "-o", f"-p {PG_PORT} -c listen_addresses=127.0.0.1 -c shared_buffers=64MB"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90,
    )  # fmt: skip
    if r.returncode:
        raise RuntimeError((WORK / "pg.log").read_text(errors="replace")[-600:])
    import psycopg

    with psycopg.connect(PG_SUPER, autocommit=True) as c:
        for role, pw, extra in (("app_rw", RW_PW, "CREATEDB"), ("share_ro", RO_PW, "")):
            if not c.execute("select 1 from pg_roles where rolname=%s", (role,)).fetchone():
                c.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' {extra}")


def start_mongo(bin_dir: Path) -> None:
    if port_open(MONGO_PORT):
        return
    data = WORK / "mongo"
    data.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [str(bin_dir / "mongod.exe"), "--dbpath", str(data), "--port", str(MONGO_PORT),
         "--bind_ip", "127.0.0.1", "--auth", "--wiredTigerCacheSizeGB", "0.25"],  # fmt: skip
        stdout=(WORK / "mongo.log").open("wb"), stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )  # fmt: skip
    for _ in range(60):
        if port_open(MONGO_PORT):
            break
        time.sleep(0.5)
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure

    time.sleep(1)
    try:
        MongoClient(f"mongodb://127.0.0.1:{MONGO_PORT}").admin.command(
            "createUser", "admin", pwd="admin_pw", roles=["root"]
        )
    except OperationFailure:
        pass  # already created on an earlier run


def engines_from_env() -> tuple[Path | None, Path | None]:
    pg, mongo = os.environ.get("ASALI_PG_BIN"), os.environ.get("ASALI_MONGO_BIN")
    return (Path(pg) if pg else None, Path(mongo) if mongo else None)


def stop() -> None:
    pg, _ = engines_from_env()
    if pg and (WORK / "pg").exists():
        _run([str(pg / "pg_ctl.exe"), "stop", "-D", str(WORK / "pg"), "-m", "fast"])
    if port_open(MONGO_PORT):
        from pymongo import MongoClient

        try:
            MongoClient(MONGO_ADMIN).admin.command("shutdown", force=True)
        except Exception:  # noqa: BLE001 - mongod closes the connection while shutting down
            pass


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    pg_dir, mongo_dir = engines_from_env()
    if action == "stop":
        stop()
    else:
        if pg_dir:
            start_postgres(pg_dir)
        if mongo_dir:
            start_mongo(mongo_dir)
        print(f"postgres :{PG_PORT} {'up' if port_open(PG_PORT) else 'down'}, "
              f"mongo :{MONGO_PORT} {'up' if port_open(MONGO_PORT) else 'down'}")  # fmt: skip
