"""Read the generated corpus and its answer key, and turn it into training data for the linker."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from asali_text.gazetteer import Gazetteer, ProductName
from asali_text.link import FEATURES, Candidate, DocFacts, featurize_all
from asali_text.mentions import extract
from asali_text.world import BatchInfo, OrgInfo, ProductInfo, ShipmentInfo, UnitInfo, World


def load_docs(corpus: Path) -> list[dict[str, Any]]:
    docs = []
    for line in (corpus / "truth.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        d["text"] = (corpus / d["split"] / d["doc_type"] / f"{d['doc_id']}.txt").read_text(encoding="utf-8")
        docs.append(d)
    return docs


def data_hash(docs: list[dict[str, Any]]) -> str:
    return hashlib.sha256("".join(d["text"] for d in docs).encode()).hexdigest()[:16]


def load_world(corpus: Path) -> World:
    raw = json.loads((corpus / "world.json").read_text(encoding="utf-8"))
    d = date.fromisoformat
    w = World()
    w.products = [ProductInfo(**p) for p in raw["products"]]
    w.batches = [
        BatchInfo(b["gtin"], b["lot"], b["maker_org"], d(b["mfg"]), d(b["expiry"]), b["status"])
        for b in raw["batches"]
    ]
    w.units = {
        k: UnitInfo(
            u["gtin"],
            u["serial"],
            u["lot"],
            u["maker_org"],
            tuple(u["chain_orgs"]),
            tuple(u["chain_cities"]),
            d(u["first"]),
            d(u["last"]),
        )
        for k, u in raw["units"].items()
    }
    w.shipments = [
        ShipmentInfo(s["from_org"], s["ref"], s["to_org"], d(s["at"]), tuple(s["gtins"]), tuple(s["cities"]))
        for s in raw["shipments"]
    ]
    w.orgs = {k: OrgInfo(**o) for k, o in raw["orgs"].items()}
    return w


def gazetteer_from(world: World) -> Gazetteer:
    return Gazetteer(
        products=tuple(ProductName(p.gtin, p.brand, p.generic, p.strength) for p in world.products),
        orgs={k: o.name for k, o in world.orgs.items() if o.org_type != "consumer"},
    )


def implied(keys: list[str], world: World) -> set[str]:
    """The keys a true link also counts for: a pack's batch and product, a batch's product."""
    out = set(keys)
    for k in keys:
        kind, rest = k.split(":", 1)
        if kind == "unit":
            u = world.units.get(rest.split("/", 1)[1])
            if u:
                out |= {f"batch:{u.gtin}/{u.lot}", f"product:{u.gtin}"}
        elif kind == "batch":
            out.add(f"product:{rest.split('/')[0]}")
    return out


def facts_for(doc: dict[str, Any], gaz: Gazetteer) -> DocFacts:
    return DocFacts(doc["owner_org"], doc["doc_type"], extract(doc["text"], gaz, 2026))


def link_rows(
    docs: list[dict[str, Any]], world: World, gaz: Gazetteer
) -> tuple[np.ndarray, np.ndarray, list[tuple[str, Candidate]]]:
    """Features and labels for every (document, candidate) pair, and which document each row belongs to."""
    xs, ys, owners = [], [], []
    for d in docs:
        cands, x = featurize_all(facts_for(d, gaz), world)
        truth = implied(d["true_links"], world)
        for c, row in zip(cands, x, strict=True):
            xs.append(row)
            ys.append(int(c.key in truth))
            owners.append((d["doc_id"], c))
    return (np.array(xs) if xs else np.zeros((0, len(FEATURES)))), np.array(ys), owners
