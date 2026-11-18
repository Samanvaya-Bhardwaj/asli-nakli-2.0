"""Without Docker: start a directory and two SQLite nodes as local processes, run the smoke test, stop them.

    uv run python infra/scripts/run_local_two_nodes.py

Plain HTTP on 127.0.0.1, simulation mode, throwaway data folders and a random join token.
This proves the node code talks to itself correctly. It is not a deployment, and not evidence of
distribution over several computers.
"""

import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from smoke_two_nodes import run

PORTS = {"directory": 18400, "shop-delhi": 18201, "dist-north": 18101}
NODES = {
    "shop-delhi": {"ORG_TYPE": "shop", "ORG_NAME": "Sharma Medicos", "HOST_NAME": "local-process-a"},
    "dist-north": {"ORG_TYPE": "distributor", "ORG_NAME": "North Star Distributors", "HOST_NAME": "local-process-b"},
}


def start(module: str, port: int, env: dict[str, str], log: Path) -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "-m", "uvicorn", module, "--factory", "--host", "127.0.0.1", "--port", str(port)]
    return subprocess.Popen(cmd, env={**os.environ, **env}, stdout=log.open("wb"), stderr=subprocess.STDOUT)


def wait_healthy(url: str, timeout_s: float = 30) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not become healthy")


def main() -> int:
    token = secrets.token_hex(16)
    work = Path(tempfile.mkdtemp(prefix="asali-local-"))
    procs: list[subprocess.Popen[bytes]] = []
    try:
        d = PORTS["directory"]
        procs.append(start("asali_directory.main:app_from_env", d,
                           {"JOIN_TOKEN": token, "ADMIN_TOKEN": secrets.token_hex(16),
                            "DATA_DIR": str(work / "directory")}, work / "directory.log"))  # fmt: skip
        wait_healthy(f"http://127.0.0.1:{d}/directory/v1/health")
        for org, extra in NODES.items():
            port = PORTS[org]
            env = {
                "ORG_ID": org, "ORG_CITY": "Delhi", "ORG_STATE": "DL", "ENGINE": "sqlite",
                "SQLITE_PATH": str(work / org / "own.sqlite"), "DATA_DIR": str(work / org),
                "DIRECTORY_URL": f"http://127.0.0.1:{d}", "JOIN_TOKEN": token,
                "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}", "ASALI_MODE": "simulation", **extra,
            }  # fmt: skip
            procs.append(start("asali_node.main:app_from_env", port, env, work / f"{org}.log"))
            wait_healthy(f"http://127.0.0.1:{port}/share/v1/health")
        orgs = httpx.get(f"http://127.0.0.1:{d}/directory/v1/orgs", timeout=5).json()
        deadline = time.monotonic() + 30
        while len(orgs) < 2 and time.monotonic() < deadline:
            time.sleep(1)
            orgs = httpx.get(f"http://127.0.0.1:{d}/directory/v1/orgs", timeout=5).json()
        print("directory lists:", [(o["org_id"], o["host_name"], o["online"]) for o in orgs])
        return run(f"http://127.0.0.1:{PORTS['shop-delhi']}", "shop-delhi",
                   f"http://127.0.0.1:{PORTS['dist-north']}", "dist-north")  # fmt: skip
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=10)
        print(f"logs in {work}")


if __name__ == "__main__":
    sys.exit(main())
