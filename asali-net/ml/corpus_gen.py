"""The document generators: one method per document type (used by generate_corpus.py)."""

import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "packages" / "asali_text"))
import templates as T  # noqa: E402
from asali_text.world import ProductInfo, ShipmentInfo, UnitInfo, World  # noqa: E402
from corpus_world import OUTSIDE_MAKERS, REC, org_name, typo, write_code, write_date, write_lot  # noqa: E402


class Gen:
    def __init__(self, world: World, state: dict[str, Any], rng: random.Random) -> None:
        self.w, self.state, self.rng = world, state, rng
        self.units = list(world.units.values())
        self.sold = {tuple(c) for b in state["bills"] for c in b["codes"]}
        self.sold_units = [u for u in self.units if (u.gtin, u.serial) in self.sold]
        self.n = 0
        self.by_batch: dict[tuple[str, str], list[UnitInfo]] = {}
        for u in self.sold_units:
            self.by_batch.setdefault((u.gtin, u.lot), []).append(u)
        eligible = sorted(k for k, v in self.by_batch.items() if len(v) >= 4)
        # Notices, recalls and most complaints concern a few problem batches, as they would in real life.
        self.problem = set(rng.sample(eligible, min(5, len(eligible))))
        self.problem_batches = [b for b in world.batches if (b.gtin, b.lot) in self.problem]
        self.quiet: dict[tuple[str, str], int] = {}

    def pick_sold(self) -> UnitInfo:
        r = self.rng
        if r.random() < 0.7:
            return r.choice(self.by_batch[r.choice(sorted(self.problem))])
        for _ in range(60):  # any other batch gets at most two complaints
            u = r.choice(self.sold_units)
            key = (u.gtin, u.lot)
            if key not in self.problem and self.quiet.get(key, 0) < 2:
                self.quiet[key] = self.quiet.get(key, 0) + 1
                return u
        return r.choice(self.by_batch[r.choice(sorted(self.problem))])

    def oname(self, org_id: str) -> str:
        REC.setdefault("org", set()).add(org_id)
        return self.w.orgs[org_id].name

    def prod(self, gtin: str) -> ProductInfo:
        return self.w.product(gtin)  # type: ignore[return-value]

    def prod_text(self, p: ProductInfo, noise: bool) -> str:
        REC.setdefault("product", set()).add(p.gtin)
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
    def _batch_doc(
        self, doc_type: str, fam: int, extra: dict[str, Any], pool: list[Any] | None = None
    ) -> tuple[str, dict[str, Any]]:
        b = self.rng.choice(pool or self.w.batches)
        p, r = self.prod(b.gtin), self.rng
        REC.setdefault("product", set()).add(b.gtin)
        slots = {
            "product": p.brand,
            "strength": p.strength,
            "lot": write_lot(b.lot, r, True),
            "mfg": b.mfg.strftime("%d/%m/%Y"),
            "expiry": b.expiry.strftime("%m/%Y"),
            "maker": self.oname(b.maker_org),
            "qa": r.choice(["R. Iyer", "S. Menon", "A. Das"]),
            "date": write_date(b.mfg + timedelta(days=r.randrange(3, 12)), r),
            "qty": r.choice([2000, 5000, 8000]),
            **extra,
        }
        return slots, {"owner": b.maker_org, "links": [b.key], "claims": {"lot": b.lot}}  # type: ignore[return-value]

    def g_coa(self, fam: int):  # type: ignore[no-untyped-def]
        fail = self.rng.random() < 0.15
        slots, truth = self._batch_doc(
            "coa",
            fam,
            {"assay": f"{self.rng.uniform(98, 101):.1f}", "dissolution": f"{self.rng.uniform(88, 97):.0f}"},
        )
        slots["result"] = (
            "Dissolution failed at 30 min. Does not comply." if fail else "Complies with specification."
        )
        truth["claims"] = {"lot": truth["claims"]["lot"], "result": "fail" if fail else "pass"}
        return self.fill(fam, "coa", slots), truth

    def g_batch_release_note(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc("batch_release_note", fam, {})
        return self.fill(fam, "batch_release_note", slots), truth

    def g_deviation_report(self, fam: int):  # type: ignore[no-untyped-def]
        issue, impact, action = self.rng.choice(T.DEVIATIONS)
        slots, truth = self._batch_doc(
            "deviation_report", fam, {"issue": issue, "impact": impact, "action": action}
        )
        return self.fill(fam, "deviation_report", slots), truth

    def g_recall_notice(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc(
            "recall_notice",
            fam,
            {"reason": self.rng.choice(T.RECALL_REASONS), "level": self.rng.choice(["class I", "class II"])},
            self.problem_batches,
        )
        return self.fill(fam, "recall_notice", slots), truth

    def g_ban_order(self, fam: int):  # type: ignore[no-untyped-def]
        slots, truth = self._batch_doc(
            "ban_order", fam, {"reason": self.rng.choice(T.BAN_REASONS)}, self.problem_batches
        )
        truth["owner"] = "regulator"
        return self.fill(fam, "ban_order", slots), truth

    # ---- operational, distributors
    def _shipment(self) -> ShipmentInfo:
        return self.rng.choice(self.w.shipments)

    def g_temperature_report(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        excursion = r.random() < 0.3
        place = r.choice(["Panipat", "Pune", "Nagpur"])
        if place != "Panipat":
            REC.setdefault("city", set()).add(place)
        base = r.uniform(4, 7)
        temps = [
            base,
            base + (r.uniform(6, 9) if excursion else r.uniform(-1, 1)),
            base + (r.uniform(5, 9) if excursion else r.uniform(-1, 1)),
        ]
        lines = "\n".join(
            f"{s.at.day}/{s.at.month} {h:02d}:{m:02d}  {t:.1f} C"
            for (h, m), t in zip([(9, 10), (11, 40), (14, 30)], temps, strict=True)
        )
        narr = (
            r.choice(T.NARRATIVES_EXCURSION).format(
                place=place, limit=8, dur=f"{r.choice([2, 3, 4])} h {r.choice([10, 20, 40])} min"
            )
            if excursion
            else r.choice(T.NARRATIVES_NORMAL)
        )
        slots = {
            "ref": s.ref,
            "from_org": self.oname(s.from_org),
            "to_org": self.oname(s.to_org),
            "logger": f"TL-{r.randrange(10, 99)}",
            "readings": lines,
            "narrative": narr,
        }
        owner = s.from_org if self.w.orgs[s.from_org].org_type == "distributor" else s.to_org
        return self.fill(fam, "temperature_report", slots), {
            "owner": owner,
            "links": [s.key],
            "claims": {"shipment_ref": s.ref, "max_temp_c": round(max(temps), 1)},
        }

    def g_delivery_note(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        slots = {
            "ref": s.ref,
            "from_org": self.oname(s.from_org),
            "to_org": self.oname(s.to_org),
            "cartons": r.randrange(2, 12),
            "vehicle": f"DL{r.randrange(1, 9)}C{r.randrange(1000, 9999)}",
            "remarks": r.choice(
                [
                    "Delivered in good condition.",
                    "Driver reported light rain.",
                    "Received by the store manager.",
                ]
            ),
        }
        owner = s.from_org if self.w.orgs[s.from_org].org_type == "distributor" else s.to_org
        return self.fill(fam, "delivery_note", slots), {
            "owner": owner,
            "links": [s.key],
            "claims": {"shipment_ref": s.ref},
        }

    def g_discrepancy_note(self, fam: int):  # type: ignore[no-untyped-def]
        s, r = self._shipment(), self.rng
        units = [u for u in self.units if s.to_org in u.chain_orgs and u.gtin in s.gtins][:6] or self.units[
            :2
        ]
        miss = r.sample(units, min(2, len(units)))
        slots = {
            "ref": s.ref,
            "expected": r.randrange(18, 40),
            "received": 0,
            "org": self.oname(s.to_org),
            "missing": ", ".join(write_code(u.serial, r, True) for u in miss),
        }
        slots["received"] = slots["expected"] - len(miss)
        return self.fill(fam, "discrepancy_note", slots), {
            "owner": s.to_org,
            "links": [s.key] + [m.key for m in miss],
            "claims": {"shipment_ref": s.ref, "expected": slots["expected"], "received": slots["received"]},
        }

    def g_damage_report(self, fam: int):  # type: ignore[no-untyped-def]
        s = self._shipment()
        slots = {"ref": s.ref, "org": self.oname(s.to_org), "damage": self.rng.choice(T.DAMAGE_TEXT)}
        return self.fill(fam, "damage_report", slots), {
            "owner": s.to_org,
            "links": [s.key],
            "claims": {"shipment_ref": s.ref},
        }

    # ---- shops and consumers
    def _pack_slots(
        self, u: UnitInfo, fam: int, noise: bool = True
    ) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
        r, p = self.rng, self.prod(u.gtin)
        shop = u.chain_orgs[-1]
        has_code = r.random() < 0.7
        bits = [f"Code {write_code(u.serial, r, noise)}."] if has_code else []
        if r.random() < 0.5:
            bits.append(f"Batch {write_lot(u.lot, r, noise)}.")
        links = [f"unit:{u.gtin}/{u.serial}"] if has_code else [f"product:{u.gtin}"]
        REC.setdefault("city", set()).add(u.chain_cities[-1])
        return (
            {
                "product": self.prod_text(p, noise),
                "shop": org_name(self.w, shop, r, noise),
                "city": u.chain_cities[-1],
                "codes": " ".join(bits),
            },
            links,
            {"purchase_city": u.chain_cities[-1], "purchase_shop": shop},
        )

    def _text_for(self, labels: list[str], hinglish: bool, fam: int) -> str:
        r = self.rng
        bank = T.ISSUE_HI if hinglish else T.ISSUE_EN
        return " ".join(
            (bank[lab][r.randrange(len(bank[lab]))] if hinglish else bank[lab][fam]) for lab in labels
        )

    def g_consumer_complaint(
        self, fam: int, unit: UnitInfo | None = None, labels: list[str] | None = None, noise: bool = True
    ):  # type: ignore[no-untyped-def]
        r = self.rng
        u = unit or self.pick_sold()
        slots, links, claims = self._pack_slots(u, fam, noise)
        hi = noise and r.random() < 0.25
        labels = labels or r.sample(list(T.ISSUE_EN)[:-1], r.choice([1, 1, 2, 3])) or ["other"]
        when = u.last + timedelta(days=r.randrange(0, 3))
        buy = r.choice(T.BUY_HI if hi else T.BUY_EN).format(
            product=slots["product"], date=write_date(when, r), shop=slots["shop"], city=slots["city"]
        )
        body = (
            buy
            + " "
            + self._text_for(labels, hi, fam)
            + (" " + r.choice(T.EXTRA_SENTENCES) if noise and r.random() < 0.2 else "")
        )
        opening = r.choice(T.OPENING_HI if hi else T.OPENING_EN) if fam % 2 == 0 else T.OPENING_EN[fam]
        closing = r.choice(T.CLOSING_HI if hi else T.CLOSING_EN) if fam % 2 == 1 else T.CLOSING_EN[fam]
        text = self.fill(
            fam,
            "consumer_complaint",
            {"opening": opening, "body": body, "codes": slots["codes"], "closing": closing},
            noise,
        )
        return text, {
            "owner": "consumer-delhi" if r.random() < 0.6 else "consumer-mumbai",
            "links": links,
            "claims": {**claims, "purchase_date": when.isoformat()},
            "labels": labels,
            "language": "hi-Latn" if hi else "en",
        }

    def g_counter_note(self, fam: int):  # type: ignore[no-untyped-def]
        r, u = self.rng, self.pick_sold()
        slots, links, claims = self._pack_slots(u, fam)
        label = r.choice(list(T.ISSUE_EN)[:-1])
        slots |= {
            "date": write_date(date.fromisoformat("2026-10-14") + timedelta(days=r.randrange(15)), r),
            "claim": T.ISSUE_EN[label][fam],
        }
        return self.fill(fam, "counter_note", slots), {
            "owner": u.chain_orgs[-1],
            "links": links,
            "claims": claims,
            "labels": [label],
        }

    def g_return_note(self, fam: int):  # type: ignore[no-untyped-def]
        r, u = self.rng, self.pick_sold()
        slots, links, claims = self._pack_slots(u, fam)
        slots |= {"bill": f"B-{r.randrange(100000, 999999)}", "reason": r.choice(T.COMPLAINT_REASONS_RETURN)}
        return self.fill(fam, "return_note", slots), {"owner": u.chain_orgs[-1], "links": links, "claims": {}}

    # ---- regulator
    def g_nsq_alert(self, fam: int):  # type: ignore[no-untyped-def]
        r = self.rng
        rows, links = [], []
        for i in range(r.randrange(5, 10)):
            if r.random() < 0.3:
                b = r.choice(self.problem_batches)
                p = self.prod(b.gtin)
                rows.append(
                    f"{i + 1}. {p.generic.title()} {p.strength} | B.No. {b.lot} | Mfd by {self.oname(b.maker_org)} | {r.choice(['Dissolution failed', 'Assay low', 'Description not as per standard'])}"
                )
                links.append(b.key)
                REC.setdefault("lot", set()).add(b.lot)
                REC.setdefault("product", set()).add(b.gtin)
            else:
                lot = f"{r.choice(['AX', 'LB', 'RZ'])}{r.randrange(100, 999)}{r.choice('ABCD')}"
                REC.setdefault("lot", set()).add(lot)
                rows.append(
                    f"{i + 1}. {r.choice(['Cefixime', 'Ranitidine', 'Losartan'])} {r.choice(['200 mg', '150 mg', '50 mg'])} | B.No. {lot} | Mfd by {r.choice(T.OUTSIDE_MAKERS) if hasattr(T, 'OUTSIDE_MAKERS') else r.choice(OUTSIDE_MAKERS)} | Assay low"
                )
        return self.fill(
            fam,
            "nsq_alert",
            {"month": r.choice(["October 2026", "September 2026", "November 2026"]), "rows": "\n".join(rows)},
            False,
        ), {"owner": "regulator", "links": links, "claims": {}}

    def g_inspection_report(self, fam: int):  # type: ignore[no-untyped-def]
        r = self.rng
        org = r.choice([k for k, o in self.w.orgs.items() if o.org_type in ("distributor", "shop")])
        findings, outcome = r.choice(T.INSPECTION_FINDINGS)
        REC.setdefault("city", set()).add(self.w.orgs[org].city)
        slots = {
            "org": self.oname(org),
            "city": self.w.orgs[org].city,
            "date": write_date(date.fromisoformat("2026-10-20") + timedelta(days=r.randrange(25)), r),
            "findings": findings,
            "outcome": outcome.replace("_", " "),
        }
        return self.fill(fam, "inspection_report", slots), {
            "owner": "regulator",
            "links": [f"org:{org}"],
            "claims": {"org": org, "outcome": outcome},
        }
