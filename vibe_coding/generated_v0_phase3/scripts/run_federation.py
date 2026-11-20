#!/usr/bin/env python3
"""
run_federation.py
-----------------
Starts Phase 3 database services and/or the coordinator as separate processes,
each database with a data directory holding only its own files.

Local simulation (everything on this machine, loopback only):
    python scripts/run_federation.py --env-file deploy/local.env

Two machines without Docker:
    Machine 2:  python scripts/run_federation.py --env-file deploy/machine2.env --only db3,db4
    Machine 1:  python scripts/run_federation.py --env-file deploy/machine1.env --only db1,db2 --coordinator

Data directories come from scripts/prepare_node_data.py (run automatically when
missing, from this project's databases). Ctrl+C stops every process it started.
"""

from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from integration.federation import runtime  # noqa: E402


def node_env(db_id: str, nodes_dir: str) -> dict:
    env = dict(os.environ)
    own = os.path.join(nodes_dir, db_id)
    env["ASALI_DB_DIR"] = os.path.join(own, "databases")
    # DB2-DB4 get a path inside their own folder that does not exist, so they can
    # never fall back to this project's DB1 document store
    env["ASALI_NOSQL_FILE"] = os.path.join(own, "nosql_store", "db1_retail_pos.json")
    env.pop("ASALI_FEDERATION", None)
    return env


def wait_health(url: str, timeout: float = 20.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + "/health", timeout=1.5) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(0.3)
    return {}


def main():
    ap = argparse.ArgumentParser(description="Start Phase 3 database services and coordinator")
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--only", help="comma-separated databases to start here (default: all four)")
    ap.add_argument("--coordinator", action="store_true", help="also start the coordinator "
                                                               "(implied when starting all four)")
    ap.add_argument("--nodes-dir", default=os.path.join(BASE, "deploy", "nodes"))
    ap.add_argument("--state-dir", default=os.path.join(BASE, "deploy", "coordinator-state"))
    args = ap.parse_args()
    runtime.bootstrap(args.env_file)
    dbs = [d.strip() for d in args.only.split(",")] if args.only else list(runtime.DB_IDS)
    with_coordinator = args.coordinator or not args.only

    missing = [d for d in dbs if not os.path.isdir(os.path.join(args.nodes_dir, d))]
    if missing:
        print(f"Preparing data directories for {', '.join(missing)} in {args.nodes_dir}")
        subprocess.check_call([sys.executable, os.path.join(BASE, "scripts", "prepare_node_data.py"),
                               "--out", args.nodes_dir] + sum((["--db", d] for d in missing), []))

    procs = []
    try:
        for d in dbs:
            p = subprocess.Popen([sys.executable, os.path.join(BASE, "api", "node_db.py"), "--db", d,
                                  "--env-file", args.env_file], env=node_env(d, args.nodes_dir), cwd=BASE)
            procs.append((d, p))
        print("\n  database   process  address                      machine          data directory")
        for d, p in procs:
            host, port = runtime.node_bind(d)
            h = wait_health(f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
            state = "up" if h else ("exited" if p.poll() is not None else "no answer")
            print(f"  {d:<9}  pid {p.pid:<5} {host + ':' + str(port):<28} "
                  f"{(h.get('machine_label') or '-'):<16} {os.path.join(args.nodes_dir, d)}  [{state}]")
        if with_coordinator:
            env = dict(os.environ, ASALI_DB_DIR=args.state_dir,
                       ASALI_NOSQL_FILE=os.path.join(args.state_dir, "no_database_here.json"))
            os.makedirs(args.state_dir, exist_ok=True)
            p = subprocess.Popen([sys.executable, os.path.join(BASE, "api", "coordinator_service.py"),
                                  "--env-file", args.env_file], env=env, cwd=BASE)
            procs.append(("coordinator", p))
            host, port = runtime.coordinator_bind()
            h = wait_health(f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
            print(f"  coordinator pid {p.pid:<5} {host + ':' + str(port):<28} holds no database  "
                  f"[{'up' if h else 'no answer'}]")
            print(f"\n  Try: python scripts/federated_demo.py --coordinator http://127.0.0.1:{port} "
                  f"\"Is MED-ASALI-009 genuine and was its cold chain maintained?\"")
        print("\n  Ctrl+C stops everything started here.")
        while all(p.poll() is None for _d, p in procs):
            time.sleep(0.5)
        for d, p in procs:
            if p.poll() is not None:
                print(f"  {d} exited with code {p.returncode}")
    except KeyboardInterrupt:
        pass
    finally:
        for _d, p in procs:
            if p.poll() is None:
                p.terminate()
        for _d, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
