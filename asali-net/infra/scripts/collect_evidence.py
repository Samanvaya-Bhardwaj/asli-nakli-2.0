"""Write the evidence of a multi-computer run (PLAN.md 16.4 step 8, TASKS.md 11.3).

    python infra/scripts/collect_evidence.py --directory-url https://192.168.1.11:8400 \
        --consumer-url https://192.168.1.11:8402 --cafile infra/out/PC-A/certs/rootCA.pem \
        --scenarios path/to/scenarios.json

Saves, under docs/evidence/four_pcs/<timestamp>/: the directory listing with host names, what every organisation
reports about itself, the latency each node measured to every other, and the result of each scenario with the
computers named in its history. It only says "multi-machine" if one verification names three or more different
computers and its mode is "network". Anything else is written down as not proven.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--directory-url", required=True)
    ap.add_argument("--consumer-url", required=True)
    ap.add_argument("--cafile")
    ap.add_argument("--scenarios", type=Path, required=True)
    args = ap.parse_args()
    verify: str | bool = args.cafile or True
    out = ROOT / "docs" / "evidence" / "four_pcs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    http = httpx.Client(timeout=30, verify=verify)

    listing = http.get(f"{args.directory_url}/directory/v1/orgs").json()
    (out / "directory.json").write_text(json.dumps(listing, indent=1))
    hosts = sorted({o["host_name"] for o in listing})

    selves, matrix = {}, {}
    for o in listing:
        try:
            selves[o["org_id"]] = http.get(f"{o['base_url']}/api/config").json()["host_name"]
            net = http.get(f"{o['base_url']}/api/network").json()
            matrix[o["org_id"]] = {x["org_id"]: x["latency_ms"] for x in net["orgs"]}
        except (httpx.HTTPError, ValueError, KeyError):
            selves[o["org_id"]] = None
    (out / "hosts.json").write_text(json.dumps(selves, indent=1))
    (out / "latency_ms.json").write_text(json.dumps(matrix, indent=1))

    expected = json.loads((ROOT / "seed" / "expected.json").read_text())
    scenarios = json.loads(args.scenarios.read_text())
    results, best = {}, 0
    for name, s in scenarios.items():
        if name not in expected or "verdict" not in expected[name]:
            continue
        reply = http.post(f"{args.consumer_url}/api/check", json={"raw": s["raw"], "city": "Delhi"}).json()
        if reply.get("status") != "done":
            results[name] = {"status": reply.get("status"), "passed": False}
            continue
        r = reply["result"]
        computers = sorted({h["served_by"]["host_name"] for h in r["history"] if h["served_by"]})
        best = max(best, len(computers)) if r["mode"] == "network" else best
        codes = [x["code"] for x in r["reasons"]]
        results[name] = {"verdict": r["verdict"], "reasons": codes, "mode": r["mode"], "computers": computers,
                         "expected": expected[name], "passed": r["verdict"] == expected[name]["verdict"] and (set(expected[name]["reasons"]) <= set(codes) if expected[name]["reasons"] else codes == [])}  # fmt: skip
    (out / "scenarios.json").write_text(json.dumps(results, indent=1))

    proven = best >= 3
    lines = [f"# Multi-computer run, {datetime.now():%d %b %Y %H:%M}", "",
             f"- Computers in the directory: {', '.join(hosts)}",
             f"- Organisations listed: {len(listing)}, online: {sum(o['online'] for o in listing)}",
             f"- Scenarios passed: {sum(r['passed'] for r in results.values())} of {len(results)}",
             f"- Most computers named in one verification (mode network): {best}", "",
             "**Multi-machine run proven.**" if proven else "**Not proven as a multi-machine run:** no verification in mode network named three different computers."]  # fmt: skip
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"evidence in {out}")
    return 0 if proven else 1


if __name__ == "__main__":
    sys.exit(main())
