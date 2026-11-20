"""Everything one computer needs for the four-computer run, in one command. Called by start-PC-*.cmd / start-PC-B.command
(which first make sure Docker is running and the Python 3.11 environment exists), but it can also be run directly:

    python infra/scripts/start_pc.py --pc PC-A            # start (or restart) this computer's organisations
    python infra/scripts/start_pc.py --pc PC-A --fresh    # reload the seeded data from the bundle first
    python infra/scripts/start_pc.py --pc PC-A --stop     # stop them

Steps, each skipped when it is already done:
  1. read infra/four_pcs.yaml and warn if this computer's address there is not one of its own addresses
  2. start PostgreSQL and MongoDB (docker compose -f infra/compose/engines.yml up -d) and wait until they accept logins
  3. build the portal (apps/portal-web/dist) when it is missing or older than its source, if npm is installed
  4. stop leftovers of an earlier run that still hold this computer's ports
  5. load the seeded data from infra/out/bundles/<PC>.zip when this computer's databases are empty, else keep the data
  6. start the organisations (run_pc.py) and stay in the foreground; Ctrl+C or closing the window stops them
"""

import argparse
import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_engines as le
import network_model
import run_pc

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "portal-web"
OURS = ("asali_node", "asali_directory")  # what our own services have on their command line


def say(msg: str) -> None:
    print(f"[start] {msg}", flush=True)


def stop_with(msg: str) -> NoReturn:
    print(f"\n[start] STOPPED: {msg}\n", flush=True)
    raise SystemExit(1)


# ---------- 1. addresses ----------
def local_ips(also_reach: str) -> set[str]:
    ips: set[str] = {"127.0.0.1"}
    with contextlib.suppress(OSError):
        ips |= {i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    for target in (
        also_reach,
        "8.8.8.8",
        "192.168.0.1",
    ):  # no packet is sent; this asks which interface would be used
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 80))
                ips.add(s.getsockname()[0])
        except OSError:
            pass
    if sys.platform != "win32":
        tool = ["ifconfig"] if shutil.which("ifconfig") else ["hostname", "-I"]
        try:
            out = subprocess.run(tool, capture_output=True, text=True, timeout=5).stdout
            ips |= {
                w.split("/")[0]
                for w in out.replace("addr:", "").split()
                if w.count(".") == 3 and w[0].isdigit()
            }
        except (OSError, subprocess.SubprocessError):
            pass
    return ips


# ---------- 2. databases ----------
def engines_up() -> None:
    if le.port_open(le.PG_PORT) and le.port_open(le.MONGO_PORT):
        say("PostgreSQL and MongoDB are already running")
    else:
        if not shutil.which("docker"):
            stop_with("Docker is not installed. Install Docker Desktop, start it, and run this again.")
        say("starting PostgreSQL and MongoDB in Docker ...")
        r = subprocess.run(
            ["docker", "compose", "-f", str(ROOT / "infra" / "compose" / "engines.yml"), "up", "-d"], cwd=ROOT
        )
        if r.returncode:
            stop_with(
                "docker compose could not start the databases (see the lines above). Is Docker Desktop running?"
            )
    import psycopg
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure

    end, last = time.monotonic() + 240, ""
    while time.monotonic() < end:
        try:
            psycopg.connect(le.PG_SUPER, connect_timeout=3).close()
            MongoClient(le.MONGO_ADMIN, serverSelectionTimeoutMS=3000).admin.command("ping")
            say("databases accept logins")
            return
        except OperationFailure as e:
            if "Authentication failed" in str(e):
                stop_with(
                    "MongoDB refuses the login: its data volume is from an earlier setup with other passwords.\n"
                    "  Reset the databases (this deletes only the database copies; the bundle reloads them):\n"
                    "    docker compose -f infra/compose/engines.yml down -v\n"
                    "  then run this again."
                )
            last = str(e)
        except Exception as e:  # a fresh container restarts once while it creates its users
            last = f"{type(e).__name__}: {e}"
        time.sleep(3)
    stop_with(f"the databases did not accept logins within 4 minutes. Last error: {last[:300]}")


# ---------- 3. portal ----------
def portal_built() -> None:
    index = WEB / "dist" / "index.html"
    npm = shutil.which("npm")
    sources = [p for p in (WEB / "src").rglob("*") if p.is_file()] + [
        WEB / "index.html",
        WEB / "package.json",
    ]
    newest = max((p.stat().st_mtime for p in sources if p.exists()), default=0)
    stale = not index.exists() or newest > index.stat().st_mtime
    if not stale:
        say("portal is built and current")
        return
    if not npm:
        if index.exists():
            say("portal source is newer than the build, but npm is not installed: serving the existing build")
        else:
            say(
                "WARNING: the portal is not built and npm is not installed. The organisations will run, but their web"
            )
            say(
                "         pages will be missing. Install Node.js, or copy apps/portal-web/dist from PC-A, then restart."
            )
        return
    if not (WEB / "node_modules").exists():
        say("installing the portal's packages (first time only) ...")
        if subprocess.run([npm, "ci"], cwd=WEB).returncode:
            stop_with("npm ci failed (see above)")
    say("building the portal ...")
    if subprocess.run([npm, "run", "build"], cwd=WEB).returncode:
        stop_with("the portal build failed (see above)")


# ---------- 4. leftovers ----------
def listeners(port: int) -> list[int]:
    if sys.platform == "win32":  # netstat's words are translated on non-English Windows; this is not
        ps = f"Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True
        ).stdout
        return sorted({int(x) for x in out.split() if x.isdigit() and x != "0"})
    out = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True
    ).stdout
    return sorted({int(x) for x in out.split()})


def command_line(pid: int) -> str:
    if sys.platform == "win32":
        ps = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True
        ).stdout.strip()
    return subprocess.run(
        ["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()


def kill(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)


def clear_ports(ports: list[int], quiet: bool = False) -> None:
    for port in ports:
        for pid in listeners(port):
            cmd = command_line(pid)
            if any(o in cmd for o in OURS):
                say(f"stopping an earlier run on port {port} (process {pid})")
                kill(pid)
            else:
                stop_with(
                    f"port {port} is used by another program (process {pid}: {cmd[:120] or 'unknown'}). Close it and run this again."
                )
    for _ in range(20):
        if not any(listeners(p) for p in ports):
            return
        time.sleep(0.5)
    if not quiet:
        stop_with(f"ports {ports} are still busy after stopping the earlier run")


# ---------- 5. data ----------
def missing_data(mine: dict, out: Path) -> list[str]:
    import psycopg
    from pymongo import MongoClient

    mongo_dbs = set(MongoClient(le.MONGO_ADMIN, serverSelectionTimeoutMS=5000).list_database_names())
    missing = []
    for org_id, org in mine.items():
        name = "asali_" + org_id.replace("-", "_")
        folder = out / "data" / org_id
        if not (folder / "keys").exists():
            missing.append(org_id)
        elif org.engine == "sqlite":
            if not (folder / "own.sqlite").exists():
                missing.append(org_id)
        elif org.engine == "postgres":
            with psycopg.connect(le.PG_SUPER, autocommit=True) as c:
                exists = c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
            if not exists:
                missing.append(org_id)
                continue
            with psycopg.connect(f"{le.PG_SUPER.rsplit('/', 1)[0]}/{name}") as c:
                n = c.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
                ).fetchone()
            if not n or n[0] == 0:
                missing.append(org_id)
        elif name not in mongo_dbs:
            missing.append(org_id)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Start this computer's share of the four-computer run.")
    ap.add_argument("--pc", required=True, choices=["PC-A", "PC-B", "PC-C", "PC-D"])
    ap.add_argument(
        "--fresh", action="store_true", help="reload the seeded data from the bundle, even if data is present"
    )
    ap.add_argument("--stop", action="store_true", help="stop this computer's organisations and exit")
    args = ap.parse_args()
    os.chdir(ROOT)

    cfg, net = run_pc.load_config(run_pc.CONFIG), network_model.load()
    pc, ip = args.pc, str(cfg["pcs"][args.pc])
    mine = net.on_pc(pc)
    ports = [o.port for o in mine.values()] + ([net.directory.port] if net.directory.pc == pc else [])
    out = ROOT / "infra" / "out" / pc

    if args.stop:
        clear_ports(ports, quiet=True)
        (out / "pids.json").unlink(missing_ok=True)
        say(
            f"{pc} stopped. The databases keep running in Docker (docker compose -f infra/compose/engines.yml stop)."
        )
        return 0

    say(f"{pc}: {', '.join(mine)}{' and the directory' if net.directory.pc == pc else ''}")
    dir_ip = str(cfg["pcs"][net.directory.pc])
    ips = local_ips(dir_ip)
    if ip not in ips:
        say(
            f"WARNING: infra/four_pcs.yaml says {pc} is {ip}, but this computer's addresses are {', '.join(sorted(ips - {'127.0.0.1'})) or 'unknown'}."
        )
        say(
            "         The other computers will not reach it. Fix the address in four_pcs.yaml on ALL four computers, then restart."
        )
    if net.directory.pc != pc:
        say(f"the directory is on {net.directory.pc} ({dir_ip}); start {net.directory.pc} first")

    engines_up()
    portal_built()
    clear_ports(ports)
    (out / "pids.json").unlink(
        missing_ok=True
    )  # never act on process ids from another run or another computer

    bundle = ROOT / "infra" / "out" / "bundles" / f"{pc}.zip"
    missing = missing_data(mine, out)
    if args.fresh or missing:
        if not bundle.exists():
            if args.fresh or len(missing) == len(mine):
                stop_with(
                    f"{bundle.relative_to(ROOT)} is missing, so the seeded data cannot be loaded. Copy it from PC-A."
                )
            say(
                f"WARNING: no data for {', '.join(missing)} and no bundle to load it from; starting with what is there"
            )
            mode = ["--keep"]
        else:
            say(
                "loading the seeded data from the bundle "
                + ("(--fresh)" if args.fresh else f"(no data yet for {', '.join(missing)})")
            )
            mode = ["--bundle", str(bundle)]
    else:
        say("data is present: keeping it")
        mode = ["--keep"]

    say("starting the organisations; leave this window open (Ctrl+C stops them)\n")
    sys.argv = ["run_pc.py", "--pc", pc, *mode]
    return run_pc.main()


if __name__ == "__main__":
    sys.exit(main())
