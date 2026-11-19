"""Run the whole network (directory and all 12 nodes) as local processes, without Docker.

    python infra/scripts/run_local_network.py            # starts everything, stays in the foreground
    python infra/scripts/run_local_network.py --stop

SIMULATION, ONE COMPUTER: plain HTTP on 127.0.0.1, real PostgreSQL and MongoDB from local_engines.py,
SQLite files, every node a separate process. It tests the software; it is not evidence of a
multi-machine run (only infra/scripts/collect_evidence.py on four PCs is). Output goes to infra/out/SIM/.
"""

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import local_engines as le
import network_model

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infra" / "out" / "SIM"
HOST = "SIM-LOCAL"


def pid_file() -> Path:
    return OUT / "pids.json"


def stop() -> None:
    if pid_file().exists():
        for pid in json.loads(pid_file().read_text()):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        pid_file().unlink()
    print("stopped")


def secrets_file() -> dict[str, object]:
    path = OUT / "secrets.json"
    if path.exists():
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    s = {"join_token": secrets.token_hex(16), "admin_token": secrets.token_hex(16),
         "staff_password": secrets.token_urlsafe(9)}  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=2))
    return s


def node_env(
    org_id: str, org: network_model.Org, s: dict[str, object], dir_url: str, data: Path
) -> dict[str, str]:
    env = {
        "ORG_ID": org_id, "ORG_TYPE": org.type, "ORG_NAME": org.name, "ORG_CITY": org.city, "ORG_STATE": org.state,
        "ENGINE": org.engine, "DIRECTORY_URL": dir_url, "JOIN_TOKEN": str(s["join_token"]),
        "PUBLIC_BASE_URL": f"http://127.0.0.1:{org.port}", "HOST_NAME": HOST, "ASALI_MODE": "simulation",
        "DATA_DIR": str(data), "BCRYPT_ROUNDS": "6",
        "STAFF_SEED_JSON": json.dumps([{"username": "staff", "password": s["staff_password"], "role": "admin",
                                        "display_name": f"{org.name} staff"}]),
    }  # fmt: skip
    if org.issuer_code:
        env["ISSUER_CODE"], env["GS1_PREFIX"] = org.issuer_code, str(org.gs1_prefix)
    if org.served_states:
        env["SERVED_STATES"] = json.dumps(org.served_states)
    if org.shop:
        env["SHOP_SETTINGS_JSON"] = json.dumps(org.shop.model_dump() | {"salt": org_id})
    if org.engine == "sqlite":
        env["SQLITE_PATH"] = str(data / "own.sqlite")
    elif org.engine == "postgres":
        env["DB_RW_URL"], env["DB_RO_URL"] = le.provision_pg("asali_" + org_id.replace("-", "_"))
    else:
        env["DB_RW_URL"], env["DB_RO_URL"] = le.provision_mongo("asali_" + org_id.replace("-", "_"))
    return env


def spawn(module: str, port: int, env: dict[str, str], log: Path) -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "-m", "uvicorn", module, "--factory", "--host", "127.0.0.1", "--port", str(port),
           "--log-level", "warning"]  # fmt: skip
    return subprocess.Popen(cmd, env={**os.environ, **env}, stdout=log.open("wb"), stderr=subprocess.STDOUT,
                            cwd=ROOT)  # fmt: skip


def wait_for(url: str, seconds: float = 60) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not answer within {seconds:.0f} s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="delete earlier data first")
    args = ap.parse_args()
    if args.stop:
        stop()
        return 0
    net = network_model.load()
    if args.fresh and (OUT / "data").exists():
        shutil.rmtree(OUT / "data")
    le.discover()
    pg_dir, mongo_dir = le.engines_from_env()
    if pg_dir:
        le.start_postgres(pg_dir)
        os.environ["PATH"] = f"{pg_dir}{os.pathsep}{os.environ['PATH']}"  # psycopg finds libpq here
    if mongo_dir:
        le.start_mongo(mongo_dir)
    s = secrets_file()
    dir_url = f"http://127.0.0.1:{net.directory.port}"
    procs: list[subprocess.Popen[bytes]] = []
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    try:
        d_env = {"JOIN_TOKEN": str(s["join_token"]), "ADMIN_TOKEN": str(s["admin_token"]),
                 "DATA_DIR": str(OUT / "data" / "directory")}  # fmt: skip
        procs.append(
            spawn(
                "asali_directory.main:app_from_env", net.directory.port, d_env, OUT / "logs" / "directory.log"
            )
        )
        wait_for(f"{dir_url}/directory/v1/health")
        for org_id, org in net.orgs.items():
            data = OUT / "data" / org_id
            data.mkdir(parents=True, exist_ok=True)
            procs.append(spawn("asali_node.main:app_from_env", org.port, node_env(org_id, org, s, dir_url, data),
                               OUT / "logs" / f"{org_id}.log"))  # fmt: skip
        for org in net.orgs.values():
            wait_for(f"http://127.0.0.1:{org.port}/share/v1/health")
        pid_file().write_text(json.dumps([p.pid for p in procs]))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            listed = httpx.get(f"{dir_url}/directory/v1/orgs", timeout=5).json()
            if sum(o["online"] for o in listed) == len(net.orgs):
                break
            time.sleep(1)
        print(f"SIMULATION on one computer: directory and {len(net.orgs)} nodes up ({sum(o['online'] for o in listed)} "
              f"online in the directory). Staff user: staff / password in {OUT / 'secrets.json'}")  # fmt: skip
        (OUT / "ready").write_text("up")
        while all(p.poll() is None for p in procs):
            time.sleep(2)
        dead = [p for p in procs if p.poll() is not None]
        print(f"a process exited ({len(dead)}); stopping")
        return 1
    finally:
        (OUT / "ready").unlink(missing_ok=True)
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    sys.exit(main())
