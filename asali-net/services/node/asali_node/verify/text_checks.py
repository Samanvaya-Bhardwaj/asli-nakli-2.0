"""Compare what a document claims with the structured record of the pack (TEXT_ML.md 6.2).

Each check says consistent, contradicts or unknown. Nothing here decides a verdict: it produces
DocSignals, and the rules in rules.py decide how much a signal weighs.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from asali_text.claims import minutes_above
from rapidfuzz import fuzz

from asali_node.canonical import Event
from asali_node.verify.models import DocSignal, Facts

MATCH, PARTIAL, NONE = "match", "partial", "no"


@dataclass(frozen=True)
class ClaimResult:
    name: str
    value: Any
    check: str  # consistent | contradicts | unknown | excursion | no_excursion | match | partial | no
    against: str = ""


def _sells(f: Facts) -> list[Event]:
    sells = [e for h in f.chain if h.view for e in h.view.events if e.event_type == "sell"]
    return sorted([*sells, *f.other_sells], key=lambda e: e.at)


def _sold_text(f: Facts, sells: list[Event]) -> str:
    return "; ".join(
        f"Sold by {f.names.get(e.org_id, e.org_id)}, {e.city} on {e.at.day} {e.at:%b %Y}" for e in sells[:3]
    )


def check_buying_claims(claims: list[dict[str, Any]], f: Facts) -> list[ClaimResult]:
    """A complaint's claims against every sale on record: it contradicts only when none of them fits."""
    sells = _sells(f)
    out = []
    for c in claims:
        name, value = c["name"], c["value"]
        against = _sold_text(f, sells) if sells else ""
        if name == "purchase_city":
            ok = None if not sells else any(value == e.city for e in sells)
        elif name == "purchase_shop":
            ok = (
                None
                if not sells
                else any(
                    value == e.org_id
                    or fuzz.token_set_ratio(str(value), f.names.get(e.org_id, "").lower()) >= 85
                    for e in sells
                )
            )
        elif name == "purchase_date":
            ok = (
                None
                if not sells
                else any(abs(date.fromisoformat(value) - e.at.date()) <= timedelta(days=3) for e in sells)
            )
        elif name == "stated_expiry":
            ok = None if f.expiry is None else value == f"{f.expiry.year:04d}-{f.expiry.month:02d}"
            against = f"Batch expires {f.expiry:%m/%Y}" if f.expiry else ""
        elif name == "stated_lot":
            ok = None if f.lot is None else value == f.lot
            against = f"This pack is from batch {f.lot}" if f.lot else ""
        else:
            continue
        out.append(
            ClaimResult(
                name, value, "unknown" if ok is None else "consistent" if ok else "contradicts", against
            )
        )
    return out


def check_temperature(claims: list[dict[str, Any]], f: Facts) -> ClaimResult | None:
    """Did the temperature report show the product above its storage limit?"""
    limit = f.product.storage_max_c if f.product else None
    if limit is None:
        return None
    by = {c["name"]: c["value"] for c in claims}
    peak = by.get("max_temp_c")
    if peak is None:
        return None
    minutes = minutes_above(by.get("readings", []), limit, by.get("stated_minutes"))
    above = peak > limit and (minutes is None or minutes > 0)
    return ClaimResult(
        "max_temp_c", peak, "excursion" if above else "no_excursion", f"Storage limit {limit:g} °C"
    )


def check_rows(claims: list[dict[str, Any]], f: Facts, maker_org: str | None) -> ClaimResult | None:
    """A notice row that names this pack's lot, and perhaps its maker."""
    best = None
    for c in claims:
        if c["name"] != "row":
            continue
        row = c["value"]
        if row["lot"] == f.lot:
            same_maker = row["manufacturer"] in (None, maker_org) and row["manufacturer"] is not None
            result = MATCH if same_maker else PARTIAL
            if best is None or result == MATCH:
                best = ClaimResult("row", row, result, row["reason"])
    return best


def signals_for(
    hit: dict[str, Any], f: Facts, conf: float, maker_org: str | None, entity_key: str = ""
) -> tuple[list[DocSignal], list[ClaimResult]]:
    """The DocSignals one linked document contributes, and the claim checks to show next to it."""
    t, doc_id, org = hit["doc_type"], hit["id"], hit["org_id"]
    quote = hit["body"].strip().splitlines()[0][:160] if hit["body"].strip() else ""
    claims = hit.get("claims", [])
    if t in ("nsq_alert", "recall_notice", "ban_order"):
        row = check_rows(claims, f, maker_org)
        if row is None:
            return [], []
        strength = conf if row.check == MATCH else min(conf, 0.85)
        kind = "official_quality_notice" if t == "nsq_alert" else "official_recall_notice"
        return [DocSignal(kind, doc_id, strength, org, quote=quote, detail={"row": row.value})], [row]  # type: ignore[arg-type]
    if t == "temperature_report":
        r = check_temperature(claims, f)
        if r and r.check == "excursion":
            return [
                DocSignal("temperature_excursion", doc_id, conf, org, quote=quote, detail={"max_c": r.value})
            ], [r]
        return [], [r] if r else []
    if t in ("consumer_complaint", "counter_note"):
        results = check_buying_claims(claims, f)
        meta = hit.get("meta", {})
        # A complaint that names only the product says nothing about this batch, so it is shown but not counted.
        specific = entity_key.split(":")[0] in ("unit", "batch", "shipment")
        sig = [DocSignal("complaint", doc_id, conf, org, quote=quote, labels=tuple(hit.get("issue_labels", [])),
                         city=meta.get("city"), reporter_key=str(meta.get("reporter") or doc_id))] if specific else []  # fmt: skip
        bad = next(
            (r for r in results if r.check == "contradicts" and r.name in ("purchase_city", "purchase_shop")),
            None,
        )
        if bad is not None and entity_key.startswith(
            "unit:"
        ):  # a batch-level complaint says nothing about this pack's sale
            says = {
                "purchase_city": f"Says bought in {bad.value}",
                "purchase_shop": "Names a different shop",
            }[bad.name]
            sig.append(
                DocSignal(
                    "contradiction", doc_id, conf, org, quote=f"{says}. {bad.against}.", city=meta.get("city")
                )
            )
        return sig, results
    return [], []
