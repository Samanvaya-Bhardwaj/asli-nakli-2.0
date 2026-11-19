"""Fill the simulated network through the portals' own APIs, as each organisation's staff would.

    python seed/seed_network.py --simulation

Pharma makes batches and packs and ships to distributors; distributors receive and forward to their shop;
shops receive and sell. Every code is typed through a scan session, about 3 % with a slip that the session
has to correct. Safe to run twice: finished steps are recorded in infra/out/SIM/seed_state.json and skipped.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
import network_model
from client import Portal, at

OUT = ROOT / "infra" / "out" / "SIM"
STATE = OUT / "seed_state.json"


def load_state() -> dict[str, Any]:
    return (
        json.loads(STATE.read_text())
        if STATE.exists()
        else {"steps": {}, "shipments": {}, "stock": {}, "bills": []}
    )


def save(state: dict[str, Any]) -> None:
    STATE.write_text(json.dumps(state, indent=1))


def portals(net: network_model.Network, password: str) -> dict[str, Portal]:
    return {k: Portal(k, f"http://127.0.0.1:{o.port}", password) for k, o in net.orgs.items()
            if o.type in ("pharma", "distributor", "shop")}  # fmt: skip


def make_catalogue(
    p: Portal, items: list[dict[str, Any]], cat: dict[str, Any], state: dict[str, Any], hour: float
) -> None:
    """Products, three batches each, 40 packs per batch. Skips what already exists."""
    have = {x["brand"]: x["gtin"] for x in p.call("GET", "/api/products")["products"]}
    for item in items:
        gtin = have.get(item["brand"]) or p.call("POST", "/api/products", json={
            "brand": item["brand"], "generic": item["generic"], "strength": item["strength"], "form": item["form"],
            "pack_size": item["pack_size"], "storage_min_c": item["min_c"], "storage_max_c": item["max_c"]})["gtin"]  # fmt: skip
        existing = [b for b in p.call("GET", f"/api/batches?gtin={gtin}")["batches"]]
        for n in range(len(existing), cat["batches_per_product"]):
            month = 6 + n  # manufactured in staggered months, expiring in 2 years
            batch = p.call("POST", "/api/batches", json={"gtin": gtin, "mfg_date": f"2026-{month:02d}-10",
                                                         "expiry_date": f"2028-{month:02d}-28",
                                                         "quantity": cat["packs_per_batch"]})  # fmt: skip
            p.call(
                "POST",
                f"/api/batches/{batch['lot']}/packs",
                json={"count": cat["packs_per_batch"], "at": at(hour)},
            )
            hour += 0.1
        state["steps"][f"catalogue:{p.org_id}"] = True


def ship_out(p: Portal, cat: dict[str, Any], state: dict[str, Any], rng: random.Random, hour: float) -> float:
    route = cat["route"]["batch_to_distributor"]
    for product in p.call("GET", "/api/products")["products"]:
        batches = p.call("GET", f"/api/batches?gtin={product['gtin']}")["batches"]
        for n, batch in enumerate(sorted(batches, key=lambda b: b["lot"])):
            key = f"ship:{p.org_id}:{batch['lot']}"
            if state["steps"].get(key):
                continue
            labels = p.call("GET", f"/api/batches/{batch['lot']}/labels")["labels"]
            take = labels[: int(len(labels) * cat["shipped_share"])]
            dist = route[n % len(route)]
            done = p.scan_session("dispatch", [(x["gtin"], x["serial"]) for x in take], rng, cat["misread_rate"],
                                  {"at": at(hour)}, to_org=dist)  # fmt: skip
            state["shipments"].setdefault(dist, []).append({"from_org": p.org_id, "shipment_id": done["shipment_id"],
                                                            "codes": [[x["gtin"], x["serial"]] for x in take]})  # fmt: skip
            state["steps"][key] = True
            hour += 0.2
    return hour


def receive_all(p: Portal, state: dict[str, Any], rng: random.Random, rate: float, hour: float) -> float:
    for sh in state["shipments"].get(p.org_id, []):
        key = f"receive:{p.org_id}:{sh['shipment_id']}"
        if state["steps"].get(key):
            continue
        p.scan_session("receive", [tuple(c) for c in sh["codes"]], rng, rate, {"at": at(hour)},  # type: ignore[misc]
                       from_org=sh["from_org"], source_ref=sh["shipment_id"])  # fmt: skip
        state["steps"][key] = True
        state["stock"].setdefault(p.org_id, []).extend(sh["codes"])
        hour += 0.2
    return hour


def forward(
    p: Portal, shop: str, share: float, state: dict[str, Any], rng: random.Random, rate: float, hour: float
) -> float:
    key = f"forward:{p.org_id}"
    if state["steps"].get(key):
        return hour
    held = state["stock"].get(p.org_id, [])
    take = held[: int(len(held) * share)]
    if take:
        done = p.scan_session("dispatch", [tuple(c) for c in take], rng, rate, {"at": at(hour)}, to_org=shop)  # type: ignore[misc]
        state["shipments"].setdefault(shop, []).append({"from_org": p.org_id, "shipment_id": done["shipment_id"],
                                                        "codes": take})  # fmt: skip
        state["stock"][p.org_id] = held[len(take) :]
    state["steps"][key] = True
    return hour + 0.2


def sell(
    p: Portal,
    share: float,
    prices: dict[str, int],
    state: dict[str, Any],
    rng: random.Random,
    rate: float,
    hour: float,
) -> None:
    key = f"sell:{p.org_id}"
    if state["steps"].get(key):
        return
    held = state["stock"].get(p.org_id, [])
    chosen = rng.sample(held, int(len(held) * share))
    for i in range(0, len(chosen), 3):  # bills of one to three packs
        part = chosen[i : i + 3]
        done = p.scan_session("sell", [tuple(c) for c in part], rng, rate,  # type: ignore[misc]
                              {"at": at(hour + i / 5), "prices": {g: prices[g] for g, _ in part}})  # fmt: skip
        state["bills"].append({"shop": p.org_id, "bill_no": done["bill_no"], "codes": part})
    sold = {tuple(c) for c in chosen}
    state["stock"][p.org_id] = [c for c in held if tuple(c) not in sold]
    state["steps"][key] = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation", action="store_true", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    net = network_model.load()
    cat = yaml.safe_load((ROOT / "seed" / "catalogue.yaml").read_text(encoding="utf-8"))
    password = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    rng, state, ps = random.Random(args.seed), load_state(), portals(net, password)
    rate = cat["misread_rate"]
    for org in ("tarang", "medivra", "kesar"):
        make_catalogue(ps[org], cat[org], cat, state, hour=0)
        save(state)
    prices = {}
    for org in ("tarang", "medivra", "kesar"):
        for prod, item in zip(ps[org].call("GET", "/api/products")["products"], cat[org], strict=True):
            prices[prod["gtin"]] = item["mrp_paise"]
    hour = 24.0
    for org in ("tarang", "medivra", "kesar"):
        hour = ship_out(ps[org], cat, state, rng, hour)
        save(state)
    for dist, shop in cat["route"]["distributor_to_shop"].items():
        hour = receive_all(ps[dist], state, rng, rate, hour + 24)
        hour = forward(ps[dist], shop, cat["forwarded_share"], state, rng, rate, hour)
        save(state)
    for shop in cat["route"]["distributor_to_shop"].values():
        hour = receive_all(ps[shop], state, rng, rate, hour + 24)
        sell(ps[shop], cat["sold_share"], prices, state, rng, rate, hour + 48)
        save(state)
    for org in ps:
        s = ps[org].call("GET", "/api/stock") if net.orgs[org].type != "pharma" else None
        print(
            f"{org:15} "
            + (
                f"stock {s['total']}"
                if s
                else f"products {len(ps[org].call('GET', '/api/products')['products'])}"
            )
        )
    print(f"bills: {len(state['bills'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
