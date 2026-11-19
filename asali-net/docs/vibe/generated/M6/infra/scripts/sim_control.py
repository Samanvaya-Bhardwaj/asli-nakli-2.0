"""Stop and start one node of the local simulation network, for outage scenarios (S8) and their tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import network_model

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infra" / "out" / "SIM"


def _pids() -> dict[str, int]:
    return json.loads((OUT / "pids.json").read_text())  # type: ignore[no-any-return]


def stop_org(org_id: str) -> None:
    subprocess.run(["taskkill", "/PID", str(_pids()[org_id]), "/T", "/F"], capture_output=True, check=False)


def start_org(org_id: str) -> None:
    """Start the node again with the environment it had, and wait until it answers."""
    org = network_model.load().orgs[org_id]
    env = json.loads((OUT / "envs" / f"{org_id}.json").read_text())
    log = (OUT / "logs" / f"{org_id}.log").open("ab")
    cmd = [sys.executable, "-m", "uvicorn", "asali_node.main:app_from_env", "--factory", "--host", "127.0.0.1",
           "--port", str(org.port), "--log-level", "warning"]  # fmt: skip
    proc = subprocess.Popen(cmd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    pids = _pids()
    pids[org_id] = proc.pid
    (OUT / "pids.json").write_text(json.dumps(pids))
    for _ in range(60):
        try:
            if httpx.get(f"http://127.0.0.1:{org.port}/share/v1/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        import time

        time.sleep(0.5)
    raise RuntimeError(f"{org_id} did not come back")
