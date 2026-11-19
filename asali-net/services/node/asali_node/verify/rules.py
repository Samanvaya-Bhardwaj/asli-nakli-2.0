"""The reasons a pack can be flagged (PLAN.md 12.2), one small function each, in the plan's order.

No network and no clock in here: everything a rule reads is in Facts. A rule that has nothing to say returns [].
"""

from collections.abc import Callable
from datetime import timedelta

from asali_node.canonical import Alert, Event
from asali_node.verify.cities import distance_km
from asali_node.verify.models import COMPLAINT_LABELS, DocSignal, Facts, Reason

SPREAD_KM, SPREAD_DAYS, SPREAD_TOTAL = 300, 7, 20
OFFICIAL_SURE, OFFICIAL_POSSIBLE, COLD_SURE, CLUSTER_SURE = 0.9, 0.6, 0.8, 0.8
COLD_MAX_C = 8


def _name(f: Facts, org_id: str) -> str:
    return f.names.get(org_id, org_id)


def _events(f: Facts) -> list[Event]:
    seen: dict[str, Event] = {}
    for hop in f.chain:
        for e in hop.view.events if hop.view else []:
            seen[e.event_id] = e
    for e in (*f.other_sells, *f.other_receives):
        seen[e.event_id] = e
    return sorted(seen.values(), key=lambda e: e.at)


def _alerts(f: Facts, *kinds: str) -> list[Alert]:
    return [a for a in f.alerts if a.kind in kinds and a.gtin == f.gtin and a.lot in (None, f.lot)]


def _signals(f: Facts, kind: str, low: float, high: float = 1.01) -> list[DocSignal]:
    return [s for s in f.doc_signals if s.kind == kind and low <= s.confidence < high]


def _doc(s: DocSignal) -> dict[str, object]:
    return {
        "kind": "document",
        "doc_id": s.doc_id,
        "org_id": s.org_id,
        "quote": s.quote,
        "confidence": s.confidence,
    }


def not_issued(f: Facts) -> list[Reason]:
    if not f.issuer_known:
        return [
            Reason("NOT_ISSUED", "do_not_use", "No organisation in the network issues codes like this one.")
        ]
    view = f.issuer_view
    if f.issuer_reachable and view is not None and not view.known:
        who = _name(f, f.chain[0].org_id)
        return [Reason("NOT_ISSUED", "do_not_use", f"{who} has no pack with this code.",
                       ({"kind": "org", "org_id": f.chain[0].org_id},))]  # fmt: skip
    return []


def destroyed(f: Facts) -> list[Reason]:
    view = f.issuer_view
    if view is not None and view.status_here == "destroyed":
        return [
            Reason("DESTROYED", "do_not_use", f"{_name(f, f.chain[0].org_id)} marked this pack as destroyed.")
        ]
    return []


def recalled(f: Facts) -> list[Reason]:
    ev: list[dict[str, object]] = [
        {"kind": "alert", "alert_id": a.alert_id, "org_id": "regulator"} for a in _alerts(f, "recall", "ban")
    ]
    ev += [_doc(s) for s in _signals(f, "official_recall_notice", OFFICIAL_SURE)]
    if f.batch_status == "recalled":
        ev.insert(0, {"kind": "org", "org_id": f.chain[0].org_id if f.chain else ""})
    if not ev:
        return []
    return [
        Reason(
            "RECALLED", "do_not_use", f"Batch {f.lot or ''} has been recalled.".replace("  ", " "), tuple(ev)
        )
    ]


def quality_failed(f: Facts) -> list[Reason]:
    ev: list[dict[str, object]] = [
        {"kind": "alert", "alert_id": a.alert_id, "org_id": "regulator"} for a in _alerts(f, "nsq")
    ]
    ev += [_doc(s) for s in _signals(f, "official_quality_notice", OFFICIAL_SURE)]
    if not ev:
        return []
    return [
        Reason(
            "QUALITY_FAILED",
            "do_not_use",
            "The drug regulator reported that this batch is not of standard quality.",
            tuple(ev),
        )
    ]


def expired(f: Facts) -> list[Reason]:
    if f.expiry is not None and f.expiry < f.today:  # the expiry date itself still counts as in date
        return [Reason("EXPIRED", "do_not_use", f"This pack expired on {f.expiry.day} {f.expiry:%b %Y}.")]
    return []


def copied_code(f: Facts) -> list[Reason]:
    events = _events(f)
    sells = [e for e in events if e.event_type == "sell"]
    orgs = {e.org_id for e in sells}
    suspicious: list[Event] = []
    if len(orgs) >= 2:
        suspicious = sells
    else:  # one shop selling the same code twice is fine only if the pack came back in between
        for org in orgs:
            last = None
            for e in (x for x in events if x.org_id == org and x.event_type in ("sell", "return")):
                if e.event_type == "sell" and last == "sell":
                    suspicious = [x for x in sells if x.org_id == org]
                last = e.event_type
    if not suspicious:
        return []
    who = " and ".join(sorted({f"{_name(f, e.org_id)}, {e.city}" for e in suspicious}))
    text = f"This code was sold by {who}. At least one pack carrying it is a copy."
    return [
        Reason(
            "COPIED_CODE",
            "do_not_use",
            text,
            tuple({"kind": "event", "org_id": e.org_id, "event_id": e.event_id} for e in suspicious),
        )
    ]


def chain_break(f: Facts) -> list[Reason]:
    out: list[Reason] = []
    on_chain = {h.org_id for h in f.chain}
    for prev, hop in zip(f.chain, f.chain[1:], strict=False):
        if hop.view is None or prev.view is None:
            continue
        sent = {(e.to_org, e.ref) for e in prev.view.events if e.event_type == "ship"}
        for e in hop.view.events:
            if e.event_type == "receive" and e.from_org == prev.org_id and (hop.org_id, e.ref) not in sent:
                out.append(_break(f, prev.org_id, hop.org_id, e))
        kinds = {e.event_type for e in hop.view.events}
        if kinds & {"sell", "ship"} and "receive" not in kinds:
            first = next(e for e in hop.view.events if e.event_type in ("sell", "ship"))
            out.append(
                _break(f, prev.org_id, hop.org_id, first, "recorded a sale or shipment with no receipt")
            )
    for e in f.other_receives:
        if e.org_id not in on_chain:
            out.append(_break(f, e.from_org or "unknown", e.org_id, e))
    for e in f.other_sells:
        if e.org_id not in on_chain and not any(r.org_id == e.org_id for r in f.other_receives):
            out.append(_break(f, "unknown", e.org_id, e, "recorded a sale with no receipt"))
    return out[:1]  # one reason is enough; the evidence carries the first break found


def _break(f: Facts, frm: str, to: str, e: Event, how: str = "") -> Reason:
    base = how or f"recorded a receipt from {_name(f, frm)} that {_name(f, frm)} has no matching dispatch for"
    return Reason(
        "CHAIN_BREAK",
        "caution",
        f"{_name(f, to)} {base}.",
        ({"kind": "event", "org_id": e.org_id, "event_id": e.event_id},),
    )


def unlicensed(f: Facts) -> list[Reason]:
    by_org = {x.org_id: x for x in f.licences}
    out: list[Reason] = []
    for hop in f.chain:
        lic, events = by_org.get(hop.org_id), (hop.view.events if hop.view else [])
        if lic is None or not events:
            continue
        on = events[0].at.date()
        if lic.status != "active" or lic.valid_to < on:
            word = lic.status if lic.status != "active" else "expired"
            out.append(Reason("UNLICENSED_HOLDER", "caution", f"{_name(f, hop.org_id)} held a {word} licence when it handled this pack.",
                              ({"kind": "licence", "org_id": hop.org_id},)))  # fmt: skip
    return out[:1]


def scan_spread(f: Facts) -> list[Reason]:
    total = sum(s.total for s in f.scan_stats)
    cities = [c for s in f.scan_stats for c in s.by_city]
    if total > SPREAD_TOTAL:
        return [
            Reason(
                "SCAN_SPREAD",
                "caution",
                f"This code has been checked {total} times, which is unusually many.",
            )
        ]
    for i, a in enumerate(cities):
        for b in cities[i + 1 :]:
            if a.city == b.city:
                continue
            gap = max(a.first_at, b.first_at) - min(a.last_at, b.last_at)
            try:
                far = distance_km(a.city, b.city) >= SPREAD_KM
            except KeyError:
                continue
            if far and gap <= timedelta(days=SPREAD_DAYS):
                return [
                    Reason(
                        "SCAN_SPREAD",
                        "caution",
                        f"This code was checked in {a.city} and {b.city} within a week.",
                    )
                ]
    return []


def cold_chain(f: Facts) -> list[Reason]:
    cold = (
        f.product is not None
        and f.product.storage_max_c is not None
        and f.product.storage_max_c <= COLD_MAX_C
    )
    hits = _signals(f, "temperature_excursion", COLD_SURE) if cold else []
    if not hits:
        return []
    return [
        Reason(
            "COLD_CHAIN",
            "caution",
            "A temperature report says this pack went above its storage limit in transit.",
            tuple(_doc(s) for s in hits),
        )
    ]


def complaint_cluster(f: Facts) -> list[Reason]:
    hits = [s for s in _signals(f, "complaint", CLUSTER_SURE) if COMPLAINT_LABELS & set(s.labels)]
    people = {s.reporter_key or s.doc_id for s in hits}
    cities = {s.city for s in hits if s.city}
    if len(people) >= 3 and len(cities) >= 2:
        return [
            Reason(
                "COMPLAINT_CLUSTER",
                "caution",
                f"{len(people)} customers in {len(cities)} cities reported problems with this batch. Not verified.",
                tuple(_doc(s) for s in hits),
            )
        ]
    return []


def text_contradiction(f: Facts) -> list[Reason]:
    hits = _signals(f, "contradiction", CLUSTER_SURE)
    return (
        [
            Reason(
                "TEXT_CONTRADICTION",
                "caution",
                hits[0].quote or "A customer's report does not match the sale records.",
                tuple(_doc(s) for s in hits),
            )
        ]
        if hits
        else []
    )


def quality_notice_possible(f: Facts) -> list[Reason]:
    if quality_failed(f):
        return []
    hits = _signals(f, "official_quality_notice", OFFICIAL_POSSIBLE, OFFICIAL_SURE)
    return (
        [
            Reason(
                "QUALITY_NOTICE_POSSIBLE",
                "caution",
                "A notice that may concern this batch was found. The link is possible, not certain.",
                tuple(_doc(s) for s in hits),
            )
        ]
        if hits
        else []
    )


def source_missing(f: Facts) -> list[Reason]:
    gone = list(f.missing) + [h.org_id for h in f.chain if h.view is None and h.org_id not in f.missing]
    if not f.issuer_reachable and f.chain and f.chain[0].org_id not in gone:
        gone.insert(0, f.chain[0].org_id)
    if not gone:
        return []
    who = ", ".join(sorted({_name(f, o) for o in gone}))
    return [
        Reason(
            "SOURCE_MISSING",
            "cannot_check",
            f"{who} did not answer.",
            tuple({"kind": "org", "org_id": o} for o in gone),
        )
    ]


RULES: list[Callable[[Facts], list[Reason]]] = [
    not_issued, destroyed, recalled, quality_failed, expired, copied_code, chain_break, unlicensed, scan_spread,
    cold_chain, complaint_cluster, text_contradiction, quality_notice_possible, source_missing,
]  # fmt: skip


def reasons(f: Facts) -> list[Reason]:
    out: list[Reason] = []
    for rule in RULES:
        out += rule(f)
    return out
