"""Share API for the regulator, the consumer nodes and documents (documents arrive with the text pipeline)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

from asali_node import deps
from asali_node.problems import Problem

router = APIRouter(prefix="/share/v1")


def caller_type(request: Request) -> str | None:
    """The caller's organisation type, from the directory view this node already holds."""
    lookup = getattr(request.app.state, "org_type_of", None)
    if lookup is not None:
        return lookup(request.state.caller_org)  # type: ignore[no-any-return]
    directory = getattr(request.app.state, "directory", None)
    for o in directory.known() if directory else []:
        if o["org_id"] == request.state.caller_org:
            return str(o["org_type"])
    return None


@router.get("/alerts")
def alerts(
    request: Request, gtin: str | None = None, lot: str | None = None, state: str | None = None
) -> dict[str, Any]:
    deps.need_type(request, "regulator")
    found = deps.ro(request).alerts(gtin, lot, state)
    return {"alerts": [a.model_dump(mode="json") for a in found]}


@router.get("/licences")
def licences(request: Request, org_ids: str | None = None) -> dict[str, Any]:
    deps.need_type(request, "regulator")
    wanted = [x for x in org_ids.split(",") if x] if org_ids is not None else None
    return {"licences": [x.model_dump(mode="json") for x in deps.ro(request).licences(wanted)]}


@router.get("/scans/{gtin}/{serial}")
def scans(request: Request, gtin: str, serial: str) -> dict[str, Any]:
    """Counts per city, no device information, times rounded to the minute (by the store)."""
    deps.need_type(request, "consumer")
    return dict(deps.ro(request).scan_stat(gtin, serial).model_dump(mode="json"))


@router.get("/scans/{gtin}/{serial}/inputs")
def scan_inputs(request: Request, gtin: str, serial: str) -> dict[str, Any]:
    """What was typed or scanned for a pack. Regulator only: slips in readings say who is mis-scanning what."""
    deps.need_type(request, "consumer")
    if caller_type(request) != "regulator":
        raise Problem(403, "Not allowed", "regulator_only", "Only the regulator can list readings.")
    return {"inputs": deps.ro(request).raw_inputs(gtin, serial)}


@router.get("/reports")
def reports(request: Request, since: datetime | None = None) -> dict[str, Any]:
    """The bulk list is for the regulator only."""
    deps.need_type(request, "consumer")
    if caller_type(request) != "regulator":
        raise Problem(403, "Not allowed", "regulator_only", "Only the regulator can list complaints in bulk.")
    return {"reports": [r.model_dump(mode="json") for r in deps.ro(request).reports(since)]}
