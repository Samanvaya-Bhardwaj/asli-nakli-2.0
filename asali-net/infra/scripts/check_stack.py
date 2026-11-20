"""Check that a stack answers: one line per organisation, then the directory's count.

    python infra/scripts/check_stack.py --simulation               # the local process simulation or the SIM stack
    python infra/scripts/check_stack.py --pc PC-C --ip 192.168.1.23 --cafile infra/out/PC-C/certs/rootCA.pem

Prints `OK <org> <host>` or `FAIL <org> <reason>`. Exit code 0 only if every organisation answered.
"""

import argparse
import sys

import httpx
import network_model


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pc")
    g.add_argument("--simulation", action="store_true")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--cafile")
    ap.add_argument("--directory-url")
    args = ap.parse_args()
    net = network_model.load()
    orgs = net.orgs if args.simulation else net.on_pc(args.pc)
    scheme = "http" if args.simulation else "https"
    verify: str | bool = args.cafile or True
    bad = 0
    for org_id, org in orgs.items():
        base = f"{scheme}://{args.ip}:{org.port}"
        try:
            health = httpx.get(f"{base}/share/v1/health", timeout=5, verify=verify)
            cfg = httpx.get(f"{base}/api/config", timeout=5, verify=verify).json()
            print(
                f"OK {org_id} {cfg['host_name']}"
                if health.status_code == 200
                else f"FAIL {org_id} HTTP {health.status_code}"
            )
            bad += health.status_code != 200
        except (httpx.HTTPError, ValueError) as e:
            print(f"FAIL {org_id} {type(e).__name__}")
            bad += 1
    directory = args.directory_url or f"{scheme}://{args.ip}:{net.directory.port}"
    try:
        listed = httpx.get(f"{directory}/directory/v1/orgs", timeout=5, verify=verify).json()
        print(f"directory lists {len(listed)} organisations, {sum(o['online'] for o in listed)} online")
    except (httpx.HTTPError, ValueError) as e:
        print(f"FAIL directory {type(e).__name__}")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
