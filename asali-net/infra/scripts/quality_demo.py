"""Phase 2 on the running simulation: audit recorded data, plant noise, clean it with the context, audit again.

    python infra/scripts/quality_demo.py

Noise is planted the way an older ledger would carry it: a recorded code changed by a look-alike slip, written
straight into the organisation's own database, bypassing the scan session that would have corrected it. This is a
simulation of legacy data on this computer; it says nothing about real data. The fixes are then applied through the
portals' own /api/quality routes, and the evidence is written to docs/evidence/quality/.
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "infra" / "out" / "SIM"
sys.path.insert(0, str(ROOT / "services" / "node"))
sys.path.insert(0, str(ROOT / "packages" / "asali_codes"))
from asali_codes.checks import luhn32_is_valid
from asali_codes.evaluate import make_noisy
from asali_node.stores.registry import open_store

PLANT = {
    "shop-delhi": 3,
    "dist-south": 3,
    "dist-north": 3,
    "shop-mumbai": 3,
    "dist-west": 3,
}  # codes to damage in each: holders only, never a maker, whose codes are made and not scanned
ORGS = [
    "tarang",
    "medivra",
    "kesar",
    "dist-north",
    "dist-west",
    "dist-south",
    "shop-delhi",
    "shop-mumbai",
    "shop-bengaluru",
    "consumer-delhi",
    "consumer-mumbai",
    "regulator",
]


def port(env: dict) -> int:
    return int(env["PUBLIC_BASE_URL"].rsplit(":", 1)[1])


def portal(org: str, password: str) -> httpx.Client:
    env = json.loads((SIM / "envs" / f"{org}.json").read_text())
    c = httpx.Client(base_url=f"http://127.0.0.1:{port(env)}", timeout=300)
    assert c.post("/api/login", json={"username": "staff", "password": password}).status_code == 200
    return c


def rw_store(org: str):  # type: ignore[no-untyped-def]
    env = json.loads((SIM / "envs" / f"{org}.json").read_text())
    return open_store(
        org, env.get("DB_RW_URL") or str(Path(env["DATA_DIR"]) / "own.sqlite"), "rw", env["ORG_CITY"]
    )


def audit_all(clients: dict[str, httpx.Client]) -> dict[str, dict]:
    return {o: c.get("/api/quality").json() for o, c in clients.items()}


def main() -> int:
    password = json.loads((SIM / "secrets.json").read_text())["staff_password"]
    clients = {o: portal(o, password) for o in ORGS}
    before = audit_all(clients)
    rng = random.Random(11)
    planted: list[dict] = []
    for org, n in PLANT.items():
        store = rw_store(org)
        try:
            serials = [r["value"] for r in store.recorded_serials() if r["rows"] >= 1]
            for true in rng.sample(serials, n):
                noisy = make_noisy(true, "lookalike1", rng)
                if luhn32_is_valid(
                    noisy
                ):  # a slip that still passes the check character would not show up here
                    continue
                changed = store.rename_serial(true, noisy)
                planted.append({"org": org, "true": true, "noisy": noisy, "rows": changed})
        finally:
            store.close()
    dirty = audit_all(clients)
    fixed: list[dict] = []
    for p in planted:
        found = next((a for a in dirty[p["org"]]["anomalies"] if a["value"] == p["noisy"]), None)
        prop = found["proposal"] if found else None
        row = {**p, "found": found is not None, "problems": found["problems"] if found else [], "proposed": prop["serial"] if prop else None,
               "proposal_cost": prop["cost"] if prop else None, "lot_fits": prop["lot_fits"] if prop else None, "proposal_correct": bool(prop and prop["serial"] == p["true"])}  # fmt: skip
        if prop:
            r = clients[p["org"]].post(
                "/api/quality/apply", json={"from_serial": p["noisy"], "to_serial": prop["serial"]}
            )
            row["applied"], row["rows_changed"] = r.status_code == 200, r.json().get("rows_changed")
        fixed.append(row)
    after = audit_all(clients)
    result = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "simulation on one computer; noise planted by script into legacy-style records",
        "anomalies_before": {o: len(v["anomalies"]) for o, v in before.items()},
        "anomalies_after_planting": {o: len(v["anomalies"]) for o, v in dirty.items()},
        "anomalies_after_cleaning": {o: len(v["anomalies"]) for o, v in after.items()},
        "records_checked": {o: v["checked"] for o, v in after.items()},
        "planted": fixed,
        "summary": {
            "planted": len(planted),
            "found": sum(f["found"] for f in fixed),
            "proposed_correctly": sum(f["proposal_correct"] for f in fixed),
            "applied": sum(bool(f.get("applied")) for f in fixed),
            "left_after": sum(len(v["anomalies"]) for v in after.values()),
            "present_before_planting": sum(len(v["anomalies"]) for v in before.values()),
        },  # fmt: skip
    }
    out = ROOT / "docs" / "evidence" / "quality"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    s = result["summary"]
    lines = ["# Cleaning noisy recorded data", "", f"Run {result['run_at']}. {result['mode']}.", "",
             f"{s['planted']} recorded codes were damaged with a look-alike slip; {s['found']} were found by the audit, {s['proposed_correctly']} got the right proposal, {s['applied']} were applied through the portal. {s['left_after']} anomalies remain, {s['present_before_planting']} of which were there before anything was planted: a code that no maker ever issued, which is a finding about a pack and not noise to clean.", "",  # fmt: skip
             "| Organisation | Damaged code | Was | Problems found | Proposed | Cost | Lot fits | Right | Rows |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for f in fixed:
        lines.append(f"| {f['org']} | {f['noisy']} | {f['true']} | {'; '.join(f['problems'])} | {f['proposed']} | {f['proposal_cost']} | {f['lot_fits']} | {f['proposal_correct']} | {f.get('rows_changed')} |")  # fmt: skip
    lines += ["", "Anomalies per organisation (before, after planting, after cleaning):", ""]
    for o in ORGS:
        lines.append(f"- {o}: {result['anomalies_before'][o]}, {result['anomalies_after_planting'][o]}, {result['anomalies_after_cleaning'][o]} (of {result['records_checked'][o]} codes recorded)")  # fmt: skip
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if s["left_after"] == s["present_before_planting"] and s["found"] == s["planted"] else 1


if __name__ == "__main__":
    sys.exit(main())
