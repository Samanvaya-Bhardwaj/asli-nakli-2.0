"""The running network as a World, and how people write codes and names (used by generate_corpus.py)."""

import hashlib
import json
import random
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "asali_text"))
import network_model  # noqa: E402
from asali_text.world import BatchInfo, OrgInfo, ProductInfo, ShipmentInfo, UnitInfo, World  # noqa: E402

OUT = ROOT / "infra" / "out" / "SIM"
ORG_VARIANTS = {"shop-delhi": ["Sharma Medicos", "sharma medical", "Sharma Medicos Lajpat Nagar", "sharma medicos"],
                "shop-mumbai": ["Apna Chemist", "apna chemists andheri", "Apna Chemist Andheri"],
                "shop-bengaluru": ["Namma Pharmacy", "namma pharmacy jayanagar"]}  # fmt: skip
OUTSIDE_MAKERS = ["Zenith Remedies", "Orchid Labs", "Vantage Pharma"]
REC: dict[str, set[str]] = {}  # what the document being written mentions, for scoring the extractor
KEYBOARD = {
    "a": "s",
    "e": "r",
    "i": "o",
    "o": "p",
    "n": "m",
    "t": "y",
    "s": "d",
    "r": "t",
    "l": "k",
    "d": "f",
}


# ---------------- the world, from the running network ----------------
def build_world(sample: int, rng: random.Random) -> tuple[World, dict[str, Any]]:
    from client import Portal

    net = network_model.load()
    pw = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    portals = {
        k: Portal(k, f"http://127.0.0.1:{o.port}", pw)
        for k, o in net.orgs.items()
        if o.type in ("pharma", "distributor", "shop")
    }
    state = json.loads((OUT / "seed_state.json").read_text())
    w = World(orgs={k: OrgInfo(k, o.name, o.type, o.city) for k, o in net.orgs.items()})
    for org, o in net.orgs.items():
        if o.type != "pharma":
            continue
        for p in portals[org].call("GET", "/api/products")["products"]:
            w.products.append(ProductInfo(p["gtin"], p["brand"], p["generic"], p["strength"], org))
            for b in portals[org].call("GET", f"/api/batches?gtin={p['gtin']}")["batches"]:
                w.batches.append(
                    BatchInfo(
                        p["gtin"],
                        b["lot"],
                        org,
                        date.fromisoformat(b["mfg_date"]),
                        date.fromisoformat(b["expiry_date"]),
                        b["status"],
                    )
                )
    codes = [tuple(c) for b in state["bills"] for c in b["codes"]] + [
        tuple(c) for held in state["stock"].values() for c in held
    ]
    by_prefix = {o.issuer_code: k for k, o in net.orgs.items() if o.issuer_code}
    ships: dict[tuple[str, str], dict[str, Any]] = {}
    for gtin, serial in rng.sample(codes, min(sample, len(codes))):
        org, chain, events = by_prefix[serial[:2]], [], []
        lot = None
        while org and len(chain) < 4:
            view = portals[org].call("GET", f"/api/unit/{gtin}/{serial}")
            if not view["known"]:
                break
            lot = lot or view["lot"]
            chain.append(org)
            events += view["events"]
            nxt = [e for e in view["events"] if e["event_type"] == "ship" and e["to_org"]]
            org = nxt[-1]["to_org"] if nxt else None
            for e in nxt:
                s = ships.setdefault(
                    (e["org_id"], e["ref"]), {"to": e["to_org"], "at": e["at"][:10], "gtins": set()}
                )
                s["gtins"].add(gtin)
        days = sorted(e["at"][:10] for e in events)
        w.units[serial] = UnitInfo(
            gtin,
            serial,
            lot or "",
            by_prefix[serial[:2]],
            tuple(chain),
            tuple(net.orgs[o].city for o in chain),
            date.fromisoformat(days[0]),
            date.fromisoformat(days[-1]),
        )
    for (frm, ref), s in ships.items():
        w.shipments.append(
            ShipmentInfo(
                frm,
                ref,
                s["to"],
                date.fromisoformat(s["at"]),
                tuple(sorted(s["gtins"])),
                (net.orgs[frm].city, net.orgs[s["to"]].city),
            )
        )
    return w, state


# ---------------- writing noise ----------------
def write_code(serial: str, rng: random.Random, noise: bool) -> str:
    REC.setdefault("serial", set()).add(serial)
    s = serial
    if noise and rng.random() < 0.15:
        i = rng.randrange(2, 11)
        s = s[:i] + {"0": "O", "1": "I", "5": "S", "8": "B"}.get(s[i], s[i]) + s[i + 1 :]
    style = rng.choice(["group", "plain", "group", "lower", "spaced"]) if noise else "group"
    grouped = f"{s[:4]}-{s[4:8]}-{s[8:]}"
    return {"group": grouped, "plain": s, "lower": grouped.lower(), "spaced": f"{s[:4]} {s[4:8]} {s[8:]}"}[
        style
    ]


def write_lot(lot: str, rng: random.Random, noise: bool) -> str:
    REC.setdefault("lot", set()).add(lot)
    if not noise:
        return lot
    r = rng.random()
    if r < 0.15:
        return lot.lower()
    if r < 0.25 and lot.startswith("TP"):
        return lot[:2] + " " + lot[2:]
    if r < 0.32:
        return lot.replace("0", "O", 1)
    return lot


def typo(text: str, rng: random.Random, p: float) -> str:
    out = []
    for tok in text.split(" "):
        if len(tok) > 4 and not any(ch.isdigit() for ch in tok) and tok.isalpha() and rng.random() < p:
            i = rng.randrange(1, len(tok) - 1)
            tok = (
                tok[:i] + KEYBOARD.get(tok[i].lower(), tok[i]) + tok[i + 1 :]
                if rng.random() < 0.5
                else tok[:i] + tok[i + 1 :]
            )
        out.append(tok)
    return " ".join(out)


def write_date(d: date, rng: random.Random) -> str:
    return rng.choice([f"{d.day} {d:%b}", f"{d:%d/%m/%Y}", f"{d.day}-{d.month}-{d:%y}", f"{d.day} {d:%b %Y}"])


def org_name(world: World, org_id: str, rng: random.Random, noise: bool) -> str:
    base = world.orgs[org_id].name
    REC.setdefault("org", set()).add(org_id)
    return rng.choice(ORG_VARIANTS[org_id]) if noise and org_id in ORG_VARIANTS else base


# ---------------- generators ----------------


def write_all(docs: list[dict[str, Any]], world: World, out: Path) -> None:
    for d in docs:
        p = out / d["split"] / d["doc_type"]
        p.mkdir(parents=True, exist_ok=True)
        (p / f"{d['doc_id']}.txt").write_text(d["text"], encoding="utf-8")
    with (out / "truth.jsonl").open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps({k: v for k, v in d.items() if k != "text"}) + "\n")
    (out / "world.json").write_text(json.dumps(asdict(world), default=str), encoding="utf-8")
    digest = hashlib.sha256(b"".join(d["text"].encode() for d in docs)).hexdigest()[:16]
    (out / "DATA_HASH").write_text(digest)


def complete_mentions(doc: dict[str, Any], world: World) -> None:
    """Add the mentions that follow from the answer key: the shipment ref, the product, the city and the shop."""
    m, claims = doc["true_mentions"], doc["true_claims"]
    if "shipment_ref" in claims:
        m["shipment_ref"] = [claims["shipment_ref"]]
    gtins = sorted(
        {
            k.split(":", 1)[1].split("/")[0]
            for k in doc["true_links"]
            if k.split(":")[0] in ("unit", "batch", "product")
        }
    )
    if gtins and doc["doc_type"] != "nsq_alert":
        m["product"] = sorted(set(m.get("product", [])) | set(gtins))
    if "purchase_city" in claims:
        m["city"] = sorted(set(m.get("city", [])) | {claims["purchase_city"]})
    if "purchase_shop" in claims:
        m["org"] = sorted(set(m.get("org", [])) | {claims["purchase_shop"]})


def keep_printed(doc: dict[str, Any], world: World) -> None:
    """The answer key only lists names the document actually prints, whichever variant it used."""
    low = doc["text"].lower()
    m = doc["true_mentions"]
    m["city"] = [c for c in m.get("city", []) if c.lower() in low]
    m["org"] = [o for o in m.get("org", []) if world.orgs[o].name.lower().split()[0] in low]
    m["product"] = [
        g
        for g in m.get("product", [])
        if (p := world.product(g)) and (p.brand.lower()[:5] in low or p.generic.lower()[:5] in low)
    ]
    doc["true_mentions"] = {k: v for k, v in m.items() if v}
