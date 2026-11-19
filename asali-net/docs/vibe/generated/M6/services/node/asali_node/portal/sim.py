"""Simulation only: record a receipt the paperwork does not cover, as a careless or dishonest shop might.

Real portals only receive against a shipment the sender recorded. The scenarios (copied codes, a broken
chain) need a pack that arrived some other way, and this is the only place that can write one.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from asali_node import deps
from asali_node.auth.staff import current_staff
from asali_node.canonical import NewReceipt, UnitRef
from asali_node.problems import Problem

router = APIRouter(prefix="/api/sim", dependencies=[Depends(current_staff)])


class ForcedReceipt(BaseModel):
    from_org: str
    source_ref: str
    units: list[UnitRef]
    at: datetime


@router.post("/force-receipt", status_code=201)
def force_receipt(body: ForcedReceipt, request: Request) -> dict[str, Any]:
    if deps.settings_of(request).asali_mode != "simulation":
        raise Problem(404, "Not found", "simulation_only", "This only exists in simulation mode.")
    deps.rw(request).record_receipt(NewReceipt(from_org=body.from_org, source_ref=body.source_ref, at=body.at,
                                               units=body.units, by="simulation"))  # fmt: skip
    return {"received": len(body.units), "source_ref": body.source_ref}
