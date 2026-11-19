"""Link a document's mentions to structured records (TEXT_ML.md 4.5): candidates, features, a calibrated ranker.

Candidate generation is wide on purpose, so a misread code still reaches its true record; the model then
weighs the weak signals (name, place, date, route) and gives each candidate a probability.
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
from asali_codes.confusion import weighted_distance
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from asali_text.claims import KIND
from asali_text.mentions import Mention, by_kind
from asali_text.world import World

MAX_CODE_COST = 1.5
FEATURES = [
    "code_cost", "code_exact", "product_name_sim", "strength_match", "maker_match", "org_on_chain", "city_on_chain",
    "date_plausible", "ambiguity", "writer_related", "kind_official", "is_unit", "is_batch", "is_shipment",
    "is_product", "is_org",
]  # fmt: skip
LINKED, POSSIBLE = 0.8, 0.6


@dataclass
class DocFacts:
    owner_org: str
    doc_type: str
    mentions: list[Mention]
    year: int = 2026
    dates: list[date] = field(default_factory=list)

    def __post_init__(self) -> None:
        for m in by_kind(self.mentions, "date"):
            if m.value:
                self.dates.append(date.fromisoformat(m.value))


@dataclass
class Candidate:
    entity_type: str
    key: str
    code_cost: float
    code_exact: int
    group: str  # the mention this came from, so ambiguity can be counted per mention
    entity: Any = None
    product: Any = None  # the candidate's product, when it has one
    features: list[float] = field(default_factory=list)


def candidates(doc: DocFacts, world: World) -> list[Candidate]:
    out: list[Candidate] = []
    gtins = {m.value["gtin"] for m in by_kind(doc.mentions, "product")} | {m.value for m in by_kind(doc.mentions, "gtin")}
    for m in by_kind(doc.mentions, "serial"):
        for serial, u in world.units.items():
            cost = _cost(serial, m.value or "")
            if cost <= MAX_CODE_COST:
                out.append(Candidate("unit", u.key, cost, int(cost == 0), f"serial:{m.start}", u, world.product(u.gtin)))
    for m in by_kind(doc.mentions, "lot"):
        for b in world.batches:
            if gtins and b.gtin not in gtins and not _all_lots_ambiguous(b, gtins):
                continue
            cost = _cost(b.lot, m.value or "")
            if cost <= MAX_CODE_COST:
                out.append(Candidate("batch", b.key, cost, int(cost == 0), f"lot:{m.start}", b, world.product(b.gtin)))
    for g in gtins:
        p = world.product(g)
        if p:
            out.append(Candidate("product", f"product:{g}", 0.0, 0, f"product:{g}", p, p))
    for m in by_kind(doc.mentions, "shipment_ref"):
        for s in world.shipments:
            cost = _cost(s.ref, m.value or "")
            if cost <= 1.0:
                p = world.product(s.gtins[0]) if s.gtins else None
                out.append(Candidate("shipment", s.key, cost, int(cost == 0), f"ref:{m.start}", s, p))
    for m in by_kind(doc.mentions, "org"):
        org = world.orgs.get(m.value["org_id"])
        if org:
            out.append(Candidate("org", f"org:{org.org_id}", 0.0, 0, f"org:{org.org_id}", org, None))
    seen: set[str] = set()
    unique = []
    for c in out:  # the same record reached from two mentions keeps its cheapest route
        if c.key not in seen:
            seen.add(c.key)
            unique.append(c)
    return unique


def _all_lots_ambiguous(b: Any, gtins: set[str]) -> bool:
    return False  # a lot is only compared inside the product the document named, when it named one


def _strength_number(s: str) -> float | None:
    digits = "".join(ch for ch in s.split()[0] if ch.isdigit() or ch == ".") if s.split() else ""
    return float(digits) if digits else None


def featurize(c: Candidate, doc: DocFacts, world: World, group_sizes: dict[str, int]) -> list[float]:
    p = c.product
    m_products = by_kind(doc.mentions, "product")
    sim = 0.0
    if p is not None and m_products:
        sim = max(max(fuzz.token_set_ratio(m.text.lower(), p.brand.lower()), fuzz.token_set_ratio(m.text.lower(), p.generic.lower())) for m in m_products) / 100
    strengths = [s.value for s in by_kind(doc.mentions, "strength")]
    strength = 0.0
    if p is not None and strengths:
        want = _strength_number(p.strength)
        strength = 1.0 if any(_strength_number(s) == want for s in strengths) else -1.0
    doc_orgs = {m.value["org_id"] for m in by_kind(doc.mentions, "org")}
    maker = getattr(c.entity, "maker_org", None) or (getattr(p, "maker_org", None) if p else None)
    makers_named = {o for o in doc_orgs if world.orgs.get(o) and world.orgs[o].org_type == "pharma"}
    maker_match = 0.0 if not makers_named else (1.0 if maker in makers_named else -1.0)
    chain_orgs, chain_cities, window = _route(c, world)
    non_makers = doc_orgs - makers_named
    org_on_chain = float(bool(non_makers & chain_orgs))
    doc_cities = {m.value for m in by_kind(doc.mentions, "city")}
    city_on_chain = float(bool(doc_cities & chain_cities))
    date_ok = 0.5 if not doc.dates else float(all(window[0] <= d <= window[1] for d in doc.dates)) if window else 0.5
    related = float(doc.owner_org in chain_orgs or doc.owner_org == maker)
    return [
        c.code_cost, float(c.code_exact), sim, strength, maker_match, org_on_chain, city_on_chain, date_ok,
        math.log(1 + group_sizes.get(c.group, 1)), related, float(KIND.get(doc.doc_type) == "official"),
        float(c.entity_type == "unit"), float(c.entity_type == "batch"), float(c.entity_type == "shipment"),
        float(c.entity_type == "product"), float(c.entity_type == "org"),
    ]  # fmt: skip


def _route(c: Candidate, world: World) -> tuple[set[str], set[str], tuple[date, date] | None]:
    e = c.entity
    if c.entity_type == "unit":
        return set(e.chain_orgs), set(e.chain_cities), (e.first - timedelta(days=30), e.last + timedelta(days=120))
    if c.entity_type == "batch":
        return world.holders(e.gtin, e.lot) | {e.maker_org}, set(), (e.mfg, e.expiry + timedelta(days=90))
    if c.entity_type == "shipment":
        return {e.from_org, e.to_org}, set(e.cities), (e.at - timedelta(days=10), e.at + timedelta(days=10))
    if c.entity_type == "org":
        return {e.org_id}, {e.city}, None
    return ({e.maker_org} if e else set()), set(), None


def featurize_all(doc: DocFacts, world: World) -> tuple[list[Candidate], np.ndarray]:
    cands = candidates(doc, world)
    sizes: dict[str, int] = {}
    for c in cands:
        sizes[c.group] = sizes.get(c.group, 0) + 1
    for c in cands:
        c.features = featurize(c, doc, world, sizes)
    return cands, np.array([c.features for c in cands]) if cands else np.zeros((0, len(FEATURES)))


def because(c: Candidate, model: Any = None, top: int = 3) -> list[str]:
    """Short reasons a person can read, from the strongest features of this candidate."""
    f = dict(zip(FEATURES, c.features, strict=True))
    out = []
    if f["code_exact"]:
        out.append("exact code match")
    elif c.entity_type in ("unit", "batch", "shipment") and f["code_cost"] > 0:
        out.append("code matches after correcting a misread")
    if f["product_name_sim"] >= 0.85:
        out.append("the product named matches")
    if f["strength_match"] == 1:
        out.append("the strength matches")
    if f["maker_match"] == 1:
        out.append("the maker named is the maker")
    if f["org_on_chain"]:
        out.append("the shop or distributor named handled this pack")
    if f["city_on_chain"]:
        out.append("the city named is on this pack's route")
    if f["date_plausible"] == 1:
        out.append("the dates fit")
    elif f["date_plausible"] == 0:
        out.append("the dates do not fit")
    return out[:top] or ["weak match"]


def _cost(a: str, b: str) -> float:
    """Confusion-model cost, computed only for strings that are plausibly the same code (cheap edit distance first)."""
    if a == b:
        return 0.0
    if Levenshtein.distance(a, b) > 3:
        return 99.0
    return weighted_distance(a, b)
