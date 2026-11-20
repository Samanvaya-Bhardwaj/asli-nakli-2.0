"""Run every scenario against the local simulation and save the results (simulation on one computer, not distribution).

    python infra/scripts/run_scenarios.py

Writes docs/evidence/simulation/results.json: for each scenario the verdict, the reasons, the mode, the computers named
in the history, and whether it matches seed/expected.json.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "infra" / "out" / "SIM"
sys.path.insert(0, str(ROOT / "seed"))
import addressing


def clear_check_history() -> None:
    """Development checks count toward the scan-spread rule (more than 20 checks of one code), so start from none."""
    import sqlite3

    for org in ("consumer-delhi",):
        path = SIM / "data" / org / "own.sqlite"
        if path.exists():
            with sqlite3.connect(path) as con:
                con.execute("DELETE FROM checks")


def main() -> int:
    ap = argparse.ArgumentParser()
    addressing.add_arguments(ap)
    args = ap.parse_args()
    if not (args.simulation or args.directory_url):
        args.simulation = True  # the original behaviour: no arguments means the local simulation
    addr = addressing.from_args(args)
    if args.simulation:
        clear_check_history()
    expected = json.loads((ROOT / "seed" / "expected.json").read_text())
    scenarios = json.loads((SIM / "scenarios.json").read_text())
    consumer = httpx.Client(base_url=addr.consumer("Delhi"), timeout=60, verify=addr.verify)
    results: dict[str, dict[str, object]] = {}
    for name, want in expected.items():
        if (
            name == "S8" or name not in scenarios
        ):  # S8 needs a node stopped: tests/network/test_scenarios.py does that
            continue
        reply = consumer.post("/api/check", json={"raw": scenarios[name]["raw"], "city": "Delhi"}).json()
        if "verdict" not in want:
            results[name] = {
                "status": reply["status"],
                "expected": want["status"],
                "passed": reply["status"] == want["status"],
            }
            continue
        r = reply["result"]
        codes = [x["code"] for x in r["reasons"]]
        results[name] = {
            "verdict": r["verdict"], "reasons": codes, "mode": r["mode"], "headline": r["headline"],
            "computers": sorted({h["served_by"]["host_name"] for h in r["history"] if h["served_by"]}),
            "documents": [d["doc_type"] for d in r["documents"]], "expected": want,
            "passed": r["verdict"] == want["verdict"] and (set(want["reasons"]) <= set(codes) if want["reasons"] else codes == []),
        }  # fmt: skip
    out = ROOT / "docs" / "evidence" / "simulation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(
            {
                "run_at": datetime.now().isoformat(timespec="seconds"),
                "mode": "simulation on one computer"
                if args.simulation
                else f"network via directory {addr.directory_url}",
                "results": results,
            },
            indent=1,
        )
    )
    for name, r in results.items():
        print(
            f"{'PASS' if r['passed'] else 'FAIL'} {name}: {r.get('verdict', r.get('status'))} {r.get('reasons', '')}"
        )
    return 0 if all(r["passed"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
