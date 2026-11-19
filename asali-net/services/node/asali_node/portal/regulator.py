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
