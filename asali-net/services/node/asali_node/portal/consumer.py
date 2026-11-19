"""Consumer portal: problem reports. (/api/check arrives with verification, M6.) No sign-in needed."""

from datetime import date, datetime
from typing import Any

from asali_text.clean import normalise, redact
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from asali_node import deps
from asali_node.canonical import NewReport
from asali_node.problems import Problem
from asali_node.stores.sqlbase import new_id

router = APIRouter(prefix="/api")


class ReportIn(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    city: str = Field(min_length=2)
    check_id: str | None = None
    gtin: str | None = None
    serial: str | None = None
    purchase_date: date | None = None
    shop_name: str | None = None
    at: datetime | None = None


@router.post("/report", status_code=201)
def report(body: ReportIn, request: Request) -> dict[str, Any]:
    clean, removed = redact(normalise(body.text))
    if len(clean.replace("[phone]", "").replace("[email]", "").strip()) < 10:
        raise Problem(
            422, "Report too short", "too_short", "Say what is wrong with the pack or the medicine."
        )
    at = deps.effective_at(request, body.at)
    doc_id = new_id("doc_")
    sink = request.app.state.documents  # the text service when it exists, otherwise a plain file store
    sink.add(doc_id, "consumer_complaint", clean, {"city": body.city, "gtin": body.gtin, "serial": body.serial,
                                                   "purchase_date": body.purchase_date.isoformat() if body.purchase_date else None,
                                                   "shop_name": body.shop_name, "at": at.isoformat()})  # fmt: skip
    report_id = deps.rw(request).record_report(
        NewReport(
            check_id=body.check_id, doc_id=doc_id, gtin=body.gtin, serial=body.serial, city=body.city, at=at
        )
    )
    return {"report_id": report_id, "doc_id": doc_id, "removed": removed}
