"""Share API, custody routes. Every one reads through the read-only store and only answers GET."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from asali_node import deps
from asali_node.canonical import ServedBy
from asali_node.problems import Problem
from asali_node.share.common import served_by

router = APIRouter(prefix="/share/v1")


def _caller(request: Request) -> str:
    return str(request.state.caller_org)


@router.get("/units/exists")
def units_exists(
    request: Request, gtin: str | None = None, serials: str = Query(min_length=1)
) -> dict[str, Any]:
    deps.need_type(request, "pharma")
    found = deps.ro(request).existing_serials(gtin, [x for x in serials.split(",") if x])
    return {"existing": sorted(found)}


@router.get("/units/by-serial/{serial}")
def unit_by_serial(request: Request, serial: str) -> dict[str, Any]:
    """Serials are unique across the network, so a consumer who typed only the serial can be routed (D5)."""
    deps.need_type(request, "pharma")
    store = deps.ro(request)
    for p in store.products():
        view = store.unit_view(p.gtin, serial)
        if view.known:
            return _with_served_by(request, view)
    raise Problem(404, "Not found", "unknown_serial", "This organisation has not issued that code.")


@router.get("/units/{gtin}/{serial}")
def unit(request: Request, gtin: str, serial: str) -> dict[str, Any]:
    deps.need_type(request, "pharma", "distributor", "shop")
    return _with_served_by(request, deps.ro(request).unit_view(gtin, serial))


def _with_served_by(request: Request, view: Any) -> dict[str, Any]:
    sb = ServedBy.model_validate(served_by(deps.settings_of(request)))
    return dict(view.model_copy(update={"served_by": sb}).model_dump(mode="json"))


@router.get("/products")
def products(request: Request) -> dict[str, Any]:
    deps.need_type(request, "pharma")
    return {"products": [p.model_dump(mode="json") for p in deps.ro(request).products()]}


@router.get("/batches")
def batches(request: Request, gtin: str | None = None) -> dict[str, Any]:
    deps.need_type(request, "pharma")
    return {"batches": [b.model_dump(mode="json") for b in deps.ro(request).batches(gtin)]}


@router.get("/shipments")
def shipments(request: Request, since: datetime | None = None) -> dict[str, Any]:
    """Only shipments addressed to the caller; nobody can list another organisation's."""
    deps.need_type(request, "pharma", "distributor")
    found = deps.ro(request).shipments_to(_caller(request), since)
    return {"shipments": [s.model_dump(mode="json") for s in found]}
