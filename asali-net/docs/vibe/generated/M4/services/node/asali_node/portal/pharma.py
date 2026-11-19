"""Pharma portal: products, batches, packs, labels, recalls, activity (PLAN.md 11.1)."""

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from asali_node import deps, packs
from asali_node.auth.staff import Session, current_staff
from asali_node.canonical import Form, NewBatch, NewProduct
from asali_node.problems import Problem

router = APIRouter(prefix="/api", dependencies=[Depends(current_staff)])


class ProductIn(BaseModel):
    brand: str = Field(min_length=1)
    generic: str = Field(min_length=1)
    strength: str = Field(min_length=1)
    form: Form
    pack_size: int = Field(gt=0)
    storage_min_c: float | None = None
    storage_max_c: float | None = None
    schedule: str | None = None


class BatchIn(BaseModel):
    gtin: str
    lot: str | None = None
    mfg_date: date
    expiry_date: date
    quantity: int = Field(gt=0)


class PacksIn(BaseModel):
    count: int = Field(gt=0, le=2000)
    at: datetime | None = None


class RecallIn(BaseModel):
    gtin: str
    lot: str
    reason: str = Field(min_length=3)
    level: Literal["class I", "class II", "class III"] = "class II"
    at: datetime | None = None


@router.get("/products")
def list_products(request: Request) -> dict[str, Any]:
    return {"products": [p.model_dump(mode="json") for p in deps.rw(request).products()]}


@router.post("/products", status_code=201)
def add_product(body: ProductIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    store, cfg = deps.rw(request), deps.settings_of(request)
    if not cfg.gs1_prefix:
        raise Problem(
            500, "Not set up", "no_gs1_prefix", "This organisation has no GS1 company prefix configured."
        )
    gtin = packs.make_gtin(cfg.gs1_prefix, len(store.products()) + 1)
    product = store.add_product(NewProduct(gtin=gtin, **body.model_dump()))
    request.app.state.activity.add(staff.username, "product", f"{product.brand} {product.strength}")
    return dict(product.model_dump(mode="json"))


@router.get("/batches")
def list_batches(request: Request, gtin: str | None = None) -> dict[str, Any]:
    return {"batches": [b.model_dump(mode="json") for b in deps.rw(request).batches(gtin)]}


@router.post("/batches", status_code=201)
def add_batch(body: BatchIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    store, cfg = deps.rw(request), deps.settings_of(request)
    if body.expiry_date <= body.mfg_date:
        raise Problem(
            422, "Invalid dates", "bad_dates", "The expiry date must be after the manufacturing date."
        )
    lot = body.lot or packs.make_lot(cfg.issuer_code or "", body.mfg_date, len(store.batches()) + 1)
    try:
        batch = store.create_batch(NewBatch(gtin=body.gtin, lot=lot, mfg_date=body.mfg_date,
                                            expiry_date=body.expiry_date, quantity=body.quantity))  # fmt: skip
    except ValueError as e:
        raise Problem(409, "Could not create the batch", "batch_refused", str(e)) from e
    request.app.state.activity.add(staff.username, "batch", lot)
    return dict(batch.model_dump(mode="json"))


@router.post("/batches/{lot:path}/packs", status_code=201)
def make_packs(
    lot: str, body: PacksIn, request: Request, staff: Session = Depends(current_staff)
) -> dict[str, Any]:
    store, cfg = deps.rw(request), deps.settings_of(request)
    batch = next((b for b in store.batches() if b.lot == lot), None)
    if batch is None:
        raise Problem(404, "Not found", "unknown_batch", f"There is no batch {lot}.")
    if batch.status != "released":
        raise Problem(
            409, "Batch is not released", "batch_not_released", "Packs can only be made for a released batch."
        )
    serials: list[str] = []
    while len(serials) < body.count:
        fresh = {packs.make_serial(cfg.issuer_code or "") for _ in range(body.count - len(serials))}
        taken = store.existing_serials(None, sorted(fresh))
        serials += sorted(fresh - taken)
    at = deps.effective_at(request, body.at)
    n = store.commission_units(batch.gtin, lot, serials, at)
    request.app.state.activity.add(staff.username, "packs", f"{n} packs in {lot}", at)
    return {"lot": lot, "created": n}


@router.get("/batches/{lot:path}/labels")
def labels(lot: str, request: Request) -> dict[str, Any]:
    """Label data for the packs of this batch that have not been shipped yet."""
    store = deps.rw(request)
    out = [
        {"gtin": s.gtin, "serial": s.serial, "lot": lot, "expiry": s.expiry.isoformat(),
         "digital_link": packs.digital_link(s.gtin, s.serial, lot, s.expiry),
         "line": packs.label_line(s.gtin, s.serial, lot, s.expiry)}
        for s in store.stock() if s.lot == lot and s.expiry
    ]  # fmt: skip
    return {"lot": lot, "labels": out}


@router.post("/recalls", status_code=201)
def recall(body: RecallIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    store = deps.rw(request)
    if not any(b.lot == body.lot and b.gtin == body.gtin for b in store.batches(body.gtin)):
        raise Problem(404, "Not found", "unknown_batch", f"There is no batch {body.lot} for that product.")
    at = deps.effective_at(request, body.at)
    store.recall_batch(body.gtin, body.lot, body.reason, body.level, at)
    hook = getattr(request.app.state, "on_recall", None)
    if hook:
        hook(body.gtin, body.lot, body.reason, body.level, at)
    request.app.state.activity.add(staff.username, "recall", f"{body.lot}: {body.reason}", at)
    return {"gtin": body.gtin, "lot": body.lot, "status": "recalled"}


@router.get("/activity")
def activity(request: Request) -> dict[str, Any]:
    return {"activity": request.app.state.activity.recent()}
