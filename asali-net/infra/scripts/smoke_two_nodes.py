"""Ask node A to fetch node B's /share/v1/org through A's signed client, and the other way round.

    python infra/scripts/smoke_two_nodes.py --a http://localhost:8201 --a-org shop-delhi \
        --b http://localhost:8101 --b-org dist-north

Needs both nodes in simulation mode (the /api/debug/ask route exists only there).
Exit code 0 when both directions answer with the other node's identity.
"""

import argparse
import json
import sys
import time

import httpx


def ask(node_url: str, org: str) -> dict[str, object]:
    r = httpx.get(f"{node_url}/api/debug/ask", params={"org": org, "path": "/share/v1/org"}, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"{node_url} asking {org}: HTTP {r.status_code} {r.text}")
    body: dict[str, object] = r.json()
    return body


def wait_until(check, timeout_s: float, what: str) -> None:
    deadline = time.monotonic() + timeout_s
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (httpx.HTTPError, RuntimeError) as e:
            last = e
        time.sleep(1)
    raise RuntimeError(f"timed out waiting for {what}: {last}")


def run(a: str, a_org: str, b: str, b_org: str) -> int:
    results = {}
    for src, dst_org, src_org in ((a, b_org, a_org), (b, a_org, b_org)):
        wait_until(lambda src=src, dst_org=dst_org: ask(src, dst_org), 60, f"{src_org} to reach {dst_org}")
        org = ask(src, dst_org)
        print(f"{src_org} asked {dst_org}:")
        print(json.dumps(org, indent=2))
        results[(src_org, dst_org)] = org["org_id"] == dst_org and bool(org["served_by"])  # type: ignore[index]
    ok = all(results.values())
    print("SMOKE OK" if ok else f"SMOKE FAILED {results}")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--a-org", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--b-org", required=True)
    args = p.parse_args()
    return run(args.a, args.a_org, args.b, args.b_org)


if __name__ == "__main__":
    sys.exit(main())
