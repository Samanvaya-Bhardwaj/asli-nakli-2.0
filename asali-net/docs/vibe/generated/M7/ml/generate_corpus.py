"""Generate the text corpus from the seeded network (TEXT_ML.md section 10).

    python ml/generate_corpus.py --seed 42 --out ml/data/generated

Reads the real packs, batches and shipments of the running simulation through the portals' own APIs, writes
documents that refer to them, and keeps an answer key (truth.jsonl): the true links, claims and labels.
Families (sentence structures) are split 4 train / 1 validation / 1 test, so the test text has phrasing the
models never saw. Same seed, same corpus.
"""

import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "seed"))
sys.path.insert(0, str(ROOT / "infra" / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "asali_text"))
import network_model  # noqa: E402
import templates as T  # noqa: E402
from asali_text.claims import KIND  # noqa: E402
from asali_text.world import BatchInfo, OrgInfo, ProductInfo, ShipmentInfo, UnitInfo, World  # noqa: E402

OUT = ROOT / "infra" / "out" / "SIM"
COUNTS = {"coa": 120, "batch_release_note": 60, "deviation_report": 40, "recall_notice": 15, "temperature_report": 120,
          "delivery_note": 80, "discrepancy_note": 40, "damage_report": 30, "counter_note": 80, "return_note": 40,
          "consumer_complaint": 400, "nsq_alert": 24, "ban_order": 6, "inspection_report": 40}  # fmt: skip
ORG_VARIANTS = {"shop-delhi": ["Sharma Medicos", "sharma medical", "Sharma Medicos Lajpat Nagar", "sharma medicos"],
                "shop-mumbai": ["Apna Chemist", "apna chemists andheri", "Apna Chemist Andheri"],
                "shop-bengaluru": ["Namma Pharmacy", "namma pharmacy jayanagar"]}  # fmt: skip
OUTSIDE_MAKERS = ["Zenith Remedies", "Orchid Labs", "Vantage Pharma"]
KEYBOARD = {"a": "s", "e": "r", "i": "o", "o": "p", "n": "m", "t": "y", "s": "d", "r": "t", "l": "k", "d": "f"}


# ---------------- the world, from the running network ----------------
def build_world(sample: int, rng: random.Random) -> tuple[World, dict[str, Any]]:
    from client import Portal

    net = network_model.load()
    pw = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    portals = {k: Portal(k, f"http://127.0.0.1:{o.port}", pw) for k, o in net.orgs.items() if o.type in ("pharma", "distributor", "shop")}
    state = json.loads((OUT / "seed_state.json").read_text())
    w = World(orgs={k: OrgInfo(k, o.name, o.type, o.city) for k, o in net.orgs.items()})
    for org, o in net.orgs.items():
        if o.type != "pharma":
            continue
        for p in portals[org].call("GET", "/api/products")["products"]:
            w.products.append(ProductInfo(p["gtin"], p["brand"], p["generic"], p["strength"], org))
            for b in portals[org].call("GET", f"/api/batches?gtin={p['gtin']}")["batches"]:
                w.batches.append(BatchInfo(p["gtin"], b["lot"], org, date.fromisoformat(b["mfg_date"]), date.fromisoformat(b["expiry_date"]), b["status"]))
    codes = [tuple(c) for b in state["bills"] for c in b["codes"]] + [tuple(c) for held in state["stock"].values() for c in held]
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
                s = ships.setdefault((e["org_id"], e["ref"]), {"to": e["to_org"], "at": e["at"][:10], "gtins": set()})
                s["gtins"].add(gtin)
        days = sorted(e["at"][:10] for e in events)
        w.units[serial] = UnitInfo(gtin, serial, lot or "", by_prefix[serial[:2]], tuple(chain), tuple(net.orgs[o].city for o in chain), date.fromisoformat(days[0]), date.fromisoformat(days[-1]))
    for (frm, ref), s in ships.items():
        w.shipments.append(ShipmentInfo(frm, ref, s["to"], date.fromisoformat(s["at"]), tuple(sorted(s["gtins"])), (net.orgs[frm].city, net.orgs[s["to"]].city)))
    return w, state


# ---------------- writing noise ----------------
def write_code(serial: str, rng: random.Random, noise: bool) -> str:
    s = serial
    if noise and rng.random() < 0.15:
        i = rng.randrange(2, 11)
        s = s[:i] + {"0": "O", "1": "I", "5": "S", "8": "B"}.get(s[i], s[i]) + s[i + 1 :]
    style = rng.choice(["group", "plain", "group", "lower", "spaced"]) if noise else "group"
    grouped = f"{s[:4]}-{s[4:8]}-{s[8:]}"
    return {"group": grouped, "plain": s, "lower": grouped.lower(), "spaced": f"{s[:4]} {s[4:8]} {s[8:]}"}[style]


def write_lot(lot: str, rng: random.Random, noise: bool) -> str:
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
            tok = tok[:i] + KEYBOARD.get(tok[i].lower(), tok[i]) + tok[i + 1 :] if rng.random() < 0.5 else tok[:i] + tok[i + 1 :]
        out.append(tok)
    return " ".join(out)


def write_date(d: date, rng: random.Random) -> str:
    return rng.choice([f"{d.day} {d:%b}", f"{d:%d/%m/%Y}", f"{d.day}-{d.month}-{d:%y}", f"{d.day} {d:%b %Y}"])


def org_name(world: World, org_id: str, rng: random.Random, noise: bool) -> str:
    base = world.orgs[org_id].name
    return rng.choice(ORG_VARIANTS[org_id]) if noise and org_id in ORG_VARIANTS else base


# ---------------- generators ----------------
class Gen:
    def __init__(self, world: World, state: dict[str, Any], rng: random.Random) -> None:
        self.w, self.state, self.rng = world, state, rng
        self.units = list(world.units.values())
        self.sold = {tuple(c) for b in state["bills"] for c in b["codes"]}
        self.sold_units = [u for u in self.units if (u.gtin, u.serial) in self.sold]
        self.n = 0

    def prod(self, gtin: str) -> ProductInfo:
        return self.w.product(gtin)  # type: ignore[return-value]

    def prod_text(self, p: ProductInfo, noise: bool) -> str:
        return self.rng.choice([p.brand, p.generic, f"{p.brand} {p.strength}"]) if noise else p.brand

    def fill(self, fam: int, doc_type: str, slots: dict[str, Any], noise: bool = True) -> str:
        frame = T.FRAMES[doc_type][fam]
        text = frame.format_map(type("D", (dict,), {"__missing__": lambda s, k: ""})(slots))
        return typo(text, self.rng, 0.03) if noise else text

    def next_id(self, doc_type: str) -> str:
        self.n += 1
        return f"{doc_type[:3]}{self.n:05d}"

    def make(self, doc_type: str, fam: int) -> tuple[str, dict[str, Any]] | None:
        return getattr(self, f"g_{doc_type}")(fam)

    # ---- official, pharma
    def _batch_doc(self, doc_type: str, fam: int, extra: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        b = self.rng.choice(self.w.batches)
        p, r = self.prod(b.gtin), self.rng
        slots = {"product": p.brand, "strength": p.strength, "lot": write_lot(b.lot, r, True), "mfg": b.mfg.strftime("%d/%m/%Y"),
                 "expiry": b.expiry.strftime("%m/%Y"), "maker": self.w.orgs[b.maker_org].name, "qa": r.choice(["R. Iyer", "S. Menon", "A. Das"]),
                 "date": write_date(b.mfg + timedelta(days=r.randrange(3, 12)), r), "qty": r.choice([2000, 5000, 8000]), **extra}
        return slots, {"owner": b.maker_org, "links": [b.key], "claims": {"lot": b.lot}}  # type: ignore[return-value]

    def g_coa(self, fam: int):  # type: ignore[no-untyped-def]
        fail = self.rng.random() < 0.15
        slots, truth = self._batch_doc("coa", fam, {"assay": f"{self.rng.uniform(98, 101):.1f}", "dissolution": f"{self.rng.uniform(88, 97):.0f}"})
        slots["result"] = "Dissolution failed at 30 min. Does not comply." if fail else "Complies with specification."
        truth["claims"] = {"lot": truth["claims"]["lot"], "result": "fail" if fail else "pass"}
        return self.fill(fam, "coa", slots), truth

    def g_batch_release_note(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc("batch_release_note", fam, {})
        return self.fill(fam, "batch_release_note", slots), truth

    def g_deviation_report(self, fam: int):  # type: ignore[no-untyped-def]
        issue, impact, action = self.rng.choice(T.DEVIATIONS)
        slots, truth = self._batch_doc("deviation_report", fam, {"issue": issue, "impact": impact, "action": action})
        return self.fill(fam, "deviation_report", slots), truth

    def g_recall_notice(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc("recall_notice", fam, {"reason": self.rng.choice(T.RECALL_REASONS), "level": self.rng.choice(["class I", "class II"])})
        return self.fill(fam, "recall_notice", slots), truth

    def g_ban_order(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc("ban_order", fam, {"reason": self.rng.choice(T.BAN_REASONS)})
        truth["owner"] = "regulator"
        return self.fill(fam, "ban_order", slots), truth

    # ---- operational, distributors
    def _shipment(self) -> ShipmentInfo:
        return self.rng.choice(self.w.shipments)

    def g_temperature_report(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        excursion = r.random() < 0.3
        base = r.uniform(4, 7)
        temps = [base, base + (r.uniform(6, 9) if excursion else r.uniform(-1, 1)), base + (r.uniform(5, 9) if excursion else r.uniform(-1, 1))]
        lines = "\n".join(f"{s.at.day}/{s.at.month} {h:02d}:{m:02d}  {t:.1f} C" for (h, m), t in zip([(9, 10), (11, 40), (14, 30)], temps, strict=True))
        narr = r.choice(T.NARRATIVES_EXCURSION).format(place=r.choice(["Panipat", "Pune", "Nagpur"]), limit=8, dur=f"{r.choice([2, 3, 4])} h {r.choice([10, 20, 40])} min") if excursion else r.choice(T.NARRATIVES_NORMAL)
        slots = {"ref": s.ref, "from_org": self.w.orgs[s.from_org].name, "to_org": self.w.orgs[s.to_org].name, "logger": f"TL-{r.randrange(10, 99)}", "readings": lines, "narrative": narr}
        owner = s.from_org if self.w.orgs[s.from_org].org_type == "distributor" else s.to_org
        return self.fill(fam, "temperature_report", slots), {"owner": owner, "links": [s.key], "claims": {"shipment_ref": s.ref, "max_temp_c": round(max(temps), 1)}}

    def g_delivery_note(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        slots = {"ref": s.ref, "from_org": self.w.orgs[s.from_org].name, "to_org": self.w.orgs[s.to_org].name, "cartons": r.randrange(2, 12),
                 "vehicle": f"DL{r.randrange(1, 9)}C{r.randrange(1000, 9999)}", "remarks": r.choice(["Delivered in good condition.", "Driver reported light rain.", "Received by the store manager."])}
        owner = s.from_org if self.w.orgs[s.from_org].org_type == "distributor" else s.to_org
        return self.fill(fam, "delivery_note", slots), {"owner": owner, "links": [s.key], "claims": {"shipment_ref": s.ref}}

    def g_discrepancy_note(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        units = [u for u in self.units if s.to_org in u.chain_orgs and u.gtin in s.gtins][:6] or self.units[:2]
        miss = r.sample(units, min(2, len(units)))
        slots = {"ref": s.ref, "expected": r.randrange(18, 40), "received": 0, "org": self.w.orgs[s.to_org].name, "missing": ", ".join(write_code(u.serial, r, True) for u in miss)}
        slots["received"] = slots["expected"] - len(miss)
        return self.fill(fam, "discrepancy_note", slots), {"owner": s.to_org, "links": [s.key] + [m.key for m in miss], "claims": {"shipment_ref": s.ref, "expected": slots["expected"], "received": slots["received"]}}

    def g_damage_report(self, fam: int):  # type: ignore[no-untyped-def]
        s = self._shipment()
        slots = {"ref": s.ref, "org": self.w.orgs[s.to_org].name, "damage": self.rng.choice(T.DAMAGE_TEXT)}
        return self.fill(fam, "damage_report", slots), {"owner": s.to_org, "links": [s.key], "claims": {"shipment_ref": s.ref}}

    # ---- shops and consumers
    def _pack_slots(self, u: UnitInfo, fam: int, noise: bool = True) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
        r, p = self.rng, self.prod(u.gtin)
        shop = u.chain_orgs[-1]
        has_code = r.random() < 0.7
        bits = [f"Code {write_code(u.serial, r, noise)}."] if has_code else []
        if r.random() < 0.5:
            bits.append(f"Batch {write_lot(u.lot, r, noise)}.")
        links = [f"unit:{u.gtin}/{u.serial}"] if has_code else [f"product:{u.gtin}"]
        return {"product": self.prod_text(p, noise), "shop": org_name(self.w, shop, r, noise), "city": u.chain_cities[-1], "codes": " ".join(bits)}, links, {"purchase_city": u.chain_cities[-1], "purchase_shop": shop}

    def _text_for(self, labels: list[str], hinglish: bool, fam: int) -> str:
        r = self.rng
        bank = T.ISSUE_HI if hinglish else T.ISSUE_EN
        return " ".join((bank[lab][r.randrange(len(bank[lab]))] if hinglish else bank[lab][fam]) for lab in labels)

    def g_consumer_complaint(self, fam: int, unit: UnitInfo | None = None, labels: list[str] | None = None, noise: bool = True):  # type: ignore[no-untyped-def]
        r = self.rng
        u = unit or r.choice(self.sold_units)
        slots, links, claims = self._pack_slots(u, fam, noise)
        hi = noise and r.random() < 0.25
        labels = labels or r.sample(list(T.ISSUE_EN)[:-1], r.choice([1, 1, 2, 3])) or ["other"]
        when = date.fromisoformat("2026-10-12") + timedelta(days=r.randrange(0, 20))
        buy = r.choice(T.BUY_HI if hi else T.BUY_EN).format(product=slots["product"], date=write_date(when, r), shop=slots["shop"], city=slots["city"])
        body = buy + " " + self._text_for(labels, hi, fam) + (" " + r.choice(T.EXTRA_SENTENCES) if noise and r.random() < 0.2 else "")
        opening = r.choice(T.OPENING_HI if hi else T.OPENING_EN) if fam % 2 == 0 else T.OPENING_EN[fam]
        closing = r.choice(T.CLOSING_HI if hi else T.CLOSING_EN) if fam % 2 == 1 else T.CLOSING_EN[fam]
        text = self.fill(fam, "consumer_complaint", {"opening": opening, "body": body, "codes": slots["codes"], "closing": closing}, noise)
        return text, {"owner": "consumer-delhi" if r.random() < 0.6 else "consumer-mumbai", "links": links, "claims": {**claims, "purchase_date": when.isoformat()}, "labels": labels, "language": "hi-Latn" if hi else "en"}

    def g_counter_note(self, fam: int):  # type: ignore[no-untyped-def]
        r, u = self.rng, self.rng.choice(self.sold_units)
        slots, links, claims = self._pack_slots(u, fam)
        label = r.choice(list(T.ISSUE_EN)[:-1])
        slots |= {"date": write_date(date.fromisoformat("2026-10-14") + timedelta(days=r.randrange(15)), r), "claim": T.ISSUE_EN[label][fam]}
        return self.fill(fam, "counter_note", slots), {"owner": u.chain_orgs[-1], "links": links, "claims": claims, "labels": [label]}

    def g_return_note(self, fam: int):  # type: ignore[no-untyped-def]
        r, u = self.rng, self.rng.choice(self.sold_units)
        slots, links, claims = self._pack_slots(u, fam)
        slots |= {"bill": f"B-{r.randrange(100000, 999999)}", "reason": r.choice(T.COMPLAINT_REASONS_RETURN)}
        return self.fill(fam, "return_note", slots), {"owner": u.chain_orgs[-1], "links": links, "claims": {}}

    # ---- regulator
    def g_nsq_alert(self, fam: int):  # type: ignore[no-untyped-def]
        r = self.rng
        rows, links = [], []
        for i in range(r.randrange(5, 10)):
            if r.random() < 0.3:
                b = r.choice(self.w.batches)
                p = self.prod(b.gtin)
                rows.append(f"{i + 1}. {p.generic.title()} {p.strength} | B.No. {b.lot} | Mfd by {self.w.orgs[b.maker_org].name} | {r.choice(['Dissolution failed', 'Assay low', 'Description not as per standard'])}")
                links.append(b.key)
            else:
                lot = f"{r.choice(['AX', 'LB', 'RZ'])}{r.randrange(100, 999)}{r.choice('ABCD')}"
                rows.append(f"{i + 1}. {r.choice(['Cefixime', 'Ranitidine', 'Losartan'])} {r.choice(['200 mg', '150 mg', '50 mg'])} | B.No. {lot} | Mfd by {r.choice(T.OUTSIDE_MAKERS) if hasattr(T, 'OUTSIDE_MAKERS') else r.choice(OUTSIDE_MAKERS)} | Assay low")
        return self.fill(fam, "nsq_alert", {"month": r.choice(["October 2026", "September 2026", "November 2026"]), "rows": "\n".join(rows)}, False), {"owner": "regulator", "links": links, "claims": {}}

    def g_inspection_report(self, fam: int):  # type: ignore[no-untyped-def]
        r = self.rng
        org = r.choice([k for k, o in self.w.orgs.items() if o.org_type in ("distributor", "shop")])
        findings, outcome = r.choice(T.INSPECTION_FINDINGS)
        slots = {"org": self.w.orgs[org].name, "city": self.w.orgs[org].city, "date": write_date(date.fromisoformat("2026-10-20") + timedelta(days=r.randrange(25)), r), "findings": findings, "outcome": outcome.replace("_", " ")}
        return self.fill(fam, "inspection_report", slots), {"owner": "regulator", "links": [f"org:{org}"], "claims": {"org": org, "outcome": outcome}}


def generate(world: World, state: dict[str, Any], seed: int, scale: float) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    g = Gen(world, state, rng)
    docs: list[dict[str, Any]] = []
    for doc_type, count in COUNTS.items():
        n = max(2, round(count * scale))
        for i in range(n):
            fam = i % T.FAMILIES
            text, truth = g.make(doc_type, fam)  # type: ignore[misc]
            split = "train" if fam in T.TRAIN else "val" if fam in T.VAL else "test"
            doc = {"doc_id": g.next_id(doc_type), "owner_org": truth.pop("owner"), "doc_type": doc_type, "kind": KIND[doc_type], "family_id": f"{doc_type}:{fam}", "split": split,
                   "text": text, "issue_labels": truth.pop("labels", []), "true_links": sorted(set(truth.pop("links"))), "true_claims": truth.pop("claims"), "duplicate_of": None, "language": truth.pop("language", "en")}
            docs.append(doc)
            if doc_type == "consumer_complaint" and rng.random() < 0.05:  # a near copy for the duplicate model
                words = text.split(" ")
                words[rng.randrange(len(words))] = rng.choice(["really", "again", "also"])
                docs.append({**doc, "doc_id": g.next_id(doc_type), "text": " ".join(words), "duplicate_of": doc["doc_id"]})
    return docs


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=ROOT / "ml" / "data" / "generated")
    ap.add_argument("--sample", type=int, default=700, help="packs to put in the world")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    world, state = build_world(args.sample, rng)
    docs = generate(world, state, args.seed, args.scale)
    args.out.mkdir(parents=True, exist_ok=True)
    write_all(docs, world, args.out)
    counts: dict[tuple[str, str], int] = {}
    for d in docs:
        counts[(d["doc_type"], d["split"])] = counts.get((d["doc_type"], d["split"]), 0) + 1
    for t in COUNTS:
        print(f"{t:20} " + "  ".join(f"{s} {counts.get((t, s), 0):4}" for s in ("train", "val", "test")))
    print(f"total {len(docs)} documents; world: {len(world.units)} packs, {len(world.batches)} batches, {len(world.shipments)} shipments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
