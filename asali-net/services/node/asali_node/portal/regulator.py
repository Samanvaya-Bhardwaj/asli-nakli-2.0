"""Regulator portal: alerts and licences (PLAN.md 11.5). Investigation arrives with verification (M6)."""

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from asali_node import deps
from asali_node.auth.staff import Session, current_staff
from asali_node.canonical import Licence, NewAlert
from asali_node.problems import Problem

router = APIRouter(prefix="/api", dependencies=[Depends(current_staff)])


class AlertIn(BaseModel):
    kind: Literal["recall", "nsq", "ban"]
    gtin: str
    lot: str | None = None
    manufacturer_org: str
    reason: str = Field(min_length=3)
    states: list[str] | None = None
    at: datetime | None = None


class LicenceIn(BaseModel):
    org_id: str
    licence_no: str
    licence_type: str
    valid_from: date
    valid_to: date
    status: Literal["active", "suspended", "cancelled"] = "active"


@router.post("/alerts", status_code=201)
def issue_alert(body: AlertIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    at = deps.effective_at(request, body.at)
    alert = deps.rw(request).add_alert(NewAlert(kind=body.kind, gtin=body.gtin, lot=body.lot,
                                                manufacturer_org=body.manufacturer_org, issued_at=at,
                                                reason=body.reason, states=body.states))  # fmt: skip
    hook = getattr(request.app.state, "on_alert", None)
    if hook:
        hook(alert)
    request.app.state.activity.add(
        staff.username, f"alert {body.kind}", f"{body.gtin} {body.lot or ''}".strip(), at
    )
    return dict(alert.model_dump(mode="json"))


@router.get("/alerts")
def list_alerts(
    request: Request, gtin: str | None = None, lot: str | None = None, state: str | None = None
) -> dict[str, Any]:
    return {"alerts": [a.model_dump(mode="json") for a in deps.rw(request).alerts(gtin, lot, state)]}


@router.get("/licences")
def list_licences(request: Request) -> dict[str, Any]:
    return {"licences": [x.model_dump(mode="json") for x in deps.rw(request).licences()]}


@router.post("/licences", status_code=201)
def set_licence(body: LicenceIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    if body.valid_to < body.valid_from:
        raise Problem(422, "Invalid dates", "bad_dates", "A licence cannot end before it starts.")
    deps.rw(request).set_licence(Licence(**body.model_dump()))
    request.app.state.activity.add(staff.username, "licence", f"{body.org_id} {body.status}")
    return {"org_id": body.org_id, "status": body.status}


class InvestigateIn(BaseModel):
    raw: str = Field(min_length=3, max_length=500)


class SimilarIn(BaseModel):
    raw: str = Field(min_length=3)


@router.post("/similar")
async def similar(body: SimilarIn, request: Request) -> dict[str, Any]:
    """Issued codes that approximately match a reading, and readings recorded against an issued code (Phase 2)."""
    from asali_node.portal.consumer import _orgs
    from asali_node.verify.similar import find_similar

    return await find_similar(request.app.state.share, _orgs(request), body.raw)


@router.post("/investigate")
async def investigate(body: InvestigateIn, request: Request) -> dict[str, Any]:
    """The same verification a consumer gets, for a staff member to look into a pack. Nothing is recorded."""
    from asali_node.portal.consumer import _orgs, verify_resolved
    from asali_node.verify.checks import resolve_input

    res = await resolve_input(body.raw, request.app.state.share, _orgs(request))
    if res.decision not in ("verify", "needs_confirmation") or res.serial is None:
        return {"status": res.decision, "message": res.message, "choices": res.choices, "read": res.read}
    if res.decision == "needs_confirmation":
        res.read["note"] = "The code was corrected from what was typed; check it against the pack."
    return {"status": "done", "result": await verify_resolved(request, res, False)}


@router.get("/complaints")
async def complaints(request: Request) -> dict[str, Any]:
    """Customer complaints from every consumer node, grouped by the batch they were linked to (TEXT_ML.md 6.5)."""
    from collections import Counter

    from asali_text.clusters import unusual

    from asali_node.network.client import SourceUnavailable

    state = request.app.state
    known = state.directory.known()
    consumers = [o["org_id"] for o in known if o["org_type"] == "consumer"]
    pharmas = [o["org_id"] for o in known if o["org_type"] == "pharma"]
    docs = await state.share.gather(
        [
            (c, "/share/v1/documents/search", {"doc_types": "consumer_complaint", "limit": 50})
            for c in consumers
        ],
        6.0,
    )
    cats = await state.share.gather(
        [(p, "/share/v1/products", None) for p in pharmas]
        + [(p, "/share/v1/batches", None) for p in pharmas],
        6.0,
    )
    names = {
        x["gtin"]: f"{x['brand']} {x['strength']}"
        for r in cats[: len(pharmas)]
        if not isinstance(r, SourceUnavailable)
        for x in r["products"]
    }
    status = {
        (b["gtin"], b["lot"]): b["status"]
        for r in cats[len(pharmas) :]
        if not isinstance(r, SourceUnavailable)
        for b in r["batches"]
    }
    groups: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for r in docs:
        if isinstance(r, SourceUnavailable):
            continue
        for h in r["hits"]:
            batch = next(
                (
                    x["entity_key"]
                    for x in h["links"]
                    if x["entity_key"].startswith("batch:") and x["confidence"] >= 0.8
                ),
                None,
            )
            if batch is None or h["body"] in seen:
                continue
            seen.add(h["body"])
            g = groups.setdefault(
                batch,
                {
                    "batch": batch.split("/", 1)[1],
                    "gtin": batch[6:].split("/")[0],
                    "count": 0,
                    "cities": set(),
                    "labels": Counter(),
                },
            )
            g["count"] += 1
            if h["meta"].get("city"):
                g["cities"].add(h["meta"]["city"])
            g["labels"].update(h["issue_labels"])
    expected = max(0.5, sum(g["count"] for g in groups.values()) / max(1, len(groups)))
    rows = [
        {"batch": g["batch"], "product": names.get(g["gtin"], g["gtin"]), "count": g["count"], "cities": sorted(g["cities"]),
         "labels": [k.replace("_", " ") for k, _ in g["labels"].most_common(3)], "unusual": unusual(g["count"], expected),
         "status": status.get((g["gtin"], g["batch"]), "unknown")}
        for g in groups.values()
    ]  # fmt: skip
    rows.sort(key=lambda r: -int(r["count"]))
    return {
        "groups": rows,
        "unusual": sum(bool(r["unusual"]) for r in rows),
        "total": sum(int(r["count"]) for r in rows),
    }
