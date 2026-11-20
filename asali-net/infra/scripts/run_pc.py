"""Run this computer's share of the network: its organisations (and the directory on PC-A), for the four-computer run.

    python infra/scripts/run_pc.py --pc PC-C --bundle infra/out/bundles/PC-C.zip   # first start, with the seeded data
    python infra/scripts/run_pc.py --pc PC-C --keep                                # later starts: keep the data
    python infra/scripts/run_pc.py --pc PC-C --empty                               # start with empty databases
    python infra/scripts/run_pc.py --pc PC-C --stop
    python infra/scripts/run_pc.py --pc PC-C --stop-org dist-west                  # the "a computer is down" demo
    python infra/scripts/run_pc.py --pc PC-C --start-org dist-west

Reads the four addresses and the shared phrase from infra/four_pcs.yaml (the same file on all four computers).
Databases: PostgreSQL and MongoDB from `docker compose -f infra/compose/engines.yml up -d` on this computer
(or the vendors' builds, see local_engines.py); SQLite files under infra/out/<PC>/data. Each organisation is its own
process on 0.0.0.0, registers with the directory on PC-A under this computer's address, and talks to the others
over HTTP with signed requests. Mode "network": no simulation shortcuts. Output under infra/out/<PC>/.
"""

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import local_engines as le
import network_model
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "infra" / "four_pcs.yaml"


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [k for k, v in cfg["pcs"].items() if not v or "FILL" in str(v)]
    if not cfg.get("team_secret") or "FILL" in cfg["team_secret"]:
        missing.append("team_secret")
    if missing:
        raise SystemExit(f"Fill in {', '.join(missing)} in {path} (the same file on all four computers).")
    return cfg


def derived(secret: str) -> dict[str, str]:
    """Everything the four computers must share, made from the one phrase they all have."""

    def h(label: str, n: int) -> str:
        return hashlib.sha256(f"asali:{label}:{secret}".encode()).hexdigest()[:n]

    return {"join_token": h("join", 32), "admin_token": h("admin", 32), "staff_password": h("staff", 12)}


def node_env(pc: str, ip: str, dir_url: str, org_id: str, org: network_model.Org, sec: dict[str, str], data: Path) -> dict[str, str]:
    env = {
        "ORG_ID": org_id, "ORG_TYPE": org.type, "ORG_NAME": org.name, "ORG_CITY": org.city, "ORG_STATE": org.state,
        "ENGINE": org.engine, "DIRECTORY_URL": dir_url, "JOIN_TOKEN": sec["join_token"],
        "PUBLIC_BASE_URL": f"http://{ip}:{org.port}", "HOST_NAME": f"{pc} ({socket.gethostname()})",
        "ASALI_MODE": "network", "DATA_DIR": str(data), "BCRYPT_ROUNDS": "8",
        "ML_MODELS_DIR": str(ROOT / "ml" / "models"), "WEB_DIR": str(ROOT / "apps" / "portal-web" / "dist"),
        "STAFF_SEED_JSON": json.dumps([{"username": "staff", "password": sec["staff_password"], "role": "admin",
                                        "display_name": f"{org.name} staff"}]),
    }  # fmt: skip
    if org.issuer_code:
        env["ISSUER_CODE"], env["GS1_PREFIX"] = org.issuer_code, str(org.gs1_prefix)
    if org.served_states:
        env["SERVED_STATES"] = json.dumps(org.served_states)
    if org.shop:
        env["SHOP_SETTINGS_JSON"] = json.dumps(org.shop.model_dump() | {"salt": org_id})
    name = "asali_" + org_id.replace("-", "_")
    if org.engine == "sqlite":
        env["SQLITE_PATH"] = str(data / "own.sqlite")
    elif org.engine == "postgres":
        env["DB_RW_URL"], env["DB_RO_URL"] = le.urls_pg(name)
    else:
        env["DB_RW_URL"], env["DB_RO_URL"] = le.urls_mongo(name)
    return env


def spawn(module: str, port: int, env: dict[str, str], log: Path) -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "-m", "uvicorn", module, "--factory", "--host", "0.0.0.0", "--port", str(port), "--log-level", "warning"]
    return subprocess.Popen(cmd, env={**os.environ, **env}, stdout=log.open("ab"), stderr=subprocess.STDOUT, cwd=ROOT)


def kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def wait_for(url: str, seconds: float, what: str) -> None:
    end, told = time.monotonic() + seconds, False
    while time.monotonic() < end:
        try:
            if httpx.get(url, timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if not told:
            print(f"waiting for {what} at {url} ...")
            told = True
        time.sleep(2)
    raise SystemExit(f"{what} did not answer at {url} within {seconds:.0f} s")


def engines_up(needed: set[str]) -> None:
    """The databases this computer's organisations need, from Docker or from the vendors' builds."""
    le.discover()
    pg_dir, mongo_dir = le.engines_from_env()
    if "postgres" in needed and not le.port_open(le.PG_PORT) and pg_dir:
        le.start_postgres(pg_dir)
    if "mongo" in needed and not le.port_open(le.MONGO_PORT) and mongo_dir:
        le.start_mongo(mongo_dir)
    if pg_dir:
        os.environ["PATH"] = f"{pg_dir}{os.pathsep}{os.environ['PATH']}"
    missing = [e for e, port in (("postgres", le.PG_PORT), ("mongo", le.MONGO_PORT)) if e in needed and not le.port_open(port)]
    if missing:
        raise SystemExit(f"{' and '.join(missing)} not running. Start them: docker compose -f infra/compose/engines.yml up -d")
    for _ in range(30):  # a fresh container takes a few seconds to accept the users it creates
        try:
            if "postgres" in needed:
                import psycopg

                psycopg.connect(le.PG_SUPER, connect_timeout=3).close()
            if "mongo" in needed:
                from pymongo import MongoClient

                MongoClient(le.MONGO_ADMIN, serverSelectionTimeoutMS=3000).admin.command("ping")
            return
        except Exception:
            time.sleep(2)
    raise SystemExit("the databases are running but do not accept connections yet; wait a minute and start again")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True, choices=["PC-A", "PC-B", "PC-C", "PC-D"])
    ap.add_argument("--config", type=Path, default=CONFIG)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--bundle", type=Path, help="load this computer's seeded data from the zip, then start")
    mode.add_argument("--keep", action="store_true", help="start with the data already here")
    mode.add_argument("--empty", action="store_true", help="start with empty databases")
    mode.add_argument("--stop", action="store_true")
    mode.add_argument("--stop-org")
    mode.add_argument("--start-org")
    args = ap.parse_args()

    cfg, net = load_config(args.config), network_model.load()
    pc, ip = args.pc, str(cfg["pcs"][args.pc])
    out = ROOT / "infra" / "out" / pc
    pids_file = out / "pids.json"
    mine = net.on_pc(pc)

    if args.stop:
        for name, pid in (json.loads(pids_file.read_text()) if pids_file.exists() else {}).items():
            kill(pid)
            print(f"stopped {name}")
        pids_file.unlink(missing_ok=True)
        return 0
    if args.stop_org:
        pids = json.loads(pids_file.read_text())
        kill(pids.pop(args.stop_org))
        pids_file.write_text(json.dumps(pids))
        print(f"stopped {args.stop_org}; checks of packs that passed through it will say Cannot check")
        return 0
    if args.start_org:
        env = json.loads((out / "envs" / f"{args.start_org}.json").read_text())
        p = spawn("asali_node.main:app_from_env", mine[args.start_org].port, env, out / "logs" / f"{args.start_org}.log")
        pids = json.loads(pids_file.read_text())
        pids[args.start_org] = p.pid
        pids_file.write_text(json.dumps(pids))
        wait_for(f"http://127.0.0.1:{mine[args.start_org].port}/share/v1/health", 120, args.start_org)
        print(f"{args.start_org} is back")
        return 0

    sec = derived(cfg["team_secret"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    (out / "envs").mkdir(exist_ok=True)
    (out / "secrets.json").write_text(json.dumps(sec, indent=2))  # the seed and scenario scripts read the password here
    engines_up({o.engine for o in mine.values()})

    if args.bundle:
        sys.path.insert(0, str(ROOT / "services" / "node"))
        import bundle

        print("loaded:", ", ".join(bundle.import_bundle(pc, args.bundle, out, {})))
    elif args.empty or not (out / "data").exists():
        for org_id, org in mine.items():
            name = "asali_" + org_id.replace("-", "_")
            if org.engine == "postgres":
                le.provision_pg(name)
            elif org.engine == "mongo":
                le.provision_mongo(name)
            (out / "data" / org_id / "own.sqlite").unlink(missing_ok=True)

    dir_ip = str(cfg["pcs"][net.directory.pc])
    dir_url = f"http://{dir_ip}:{net.directory.port}"
    procs: dict[str, subprocess.Popen[bytes]] = {}
    if net.directory.pc == pc:
        d_env = {"JOIN_TOKEN": sec["join_token"], "ADMIN_TOKEN": sec["admin_token"], "DATA_DIR": str(out / "data" / "directory")}
        procs["directory"] = spawn("asali_directory.main:app_from_env", net.directory.port, d_env, out / "logs" / "directory.log")
    wait_for(f"{dir_url}/directory/v1/health", 600, "the directory on PC-A")
    for org_id, org in mine.items():
        data = out / "data" / org_id
        data.mkdir(parents=True, exist_ok=True)
        (data / "directory_cache.json").unlink(missing_ok=True)
        env = node_env(pc, ip, dir_url, org_id, org, sec, data)
        (out / "envs" / f"{org_id}.json").write_text(json.dumps(env))
        procs[org_id] = spawn("asali_node.main:app_from_env", org.port, env, out / "logs" / f"{org_id}.log")
    for org_id, org in mine.items():
        wait_for(f"http://127.0.0.1:{org.port}/share/v1/health", 240, org_id)
    pids_file.write_text(json.dumps({k: p.pid for k, p in procs.items()}))

    print(f"\n{pc} ({socket.gethostname()}, {ip}) is up. Organisations here:")
    for org_id, org in mine.items():
        print(f"  {org.name:28} http://{ip}:{org.port}")
    listed = httpx.get(f"{dir_url}/directory/v1/orgs", timeout=10).json()
    print(f"The directory at {dir_url} lists {len(listed)} organisations, {sum(o['online'] for o in listed)} online.")
    print(f"Staff login on every portal: staff / {sec['staff_password']}")
    print("Leave this window open. Ctrl+C stops this computer's organisations.")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs.values():
            p.terminate()
        pids_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
