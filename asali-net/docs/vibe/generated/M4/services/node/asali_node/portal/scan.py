"""Scan sessions over HTTP (TASKS.md 4.4): dispatch, receive, sell and return."""

import hashlib
import re
from collections.abc import Collection
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from asali_node import deps
from asali_node.auth.staff import Session, current_staff
from asali_node.canonical import (
    NewDispatch,
    NewReceipt,
    NewReturn,
    NewSale,
    NewShipment,
    SaleLine,
    ScanCorrection,
    UnitRef,
)
from asali_node.network.client import SourceUnavailable
from asali_node.problems import Problem
from asali_node.scan_sessions import Kind, ScanSession, SessionTable
from asali_node.stores.sqlbase import new_id

router = APIRouter(prefix="/api/scan", dependencies=[Depends(current_staff)])
ALLOWED: dict[str, set[str]] = {
    "pharma": {"dispatch"},
    "distributor": {"receive", "dispatch"},
    "shop": {"receive", "sell", "return"},
}


class NewSession(BaseModel):
    kind: Kind
    to_org: str | None = None
    from_org: str | None = None
    source_ref: str | None = None


class ReadBody(BaseModel):
    raw: str
    source: Literal["wedge", "camera", "typed"] = "typed"


class Choose(BaseModel):
    serial: str


class Finish(BaseModel):
    at: datetime | None = None
    prices: dict[str, int] | None = None  # sell: paise per pack, by GTIN
    customer_last4: str | None = None  # sell: hashed with the shop's salt before it is saved
    bill_no: str | None = None
    reason: str | None = None  # return


def issuer_codes(request: Request) -> Collection[str]:
    fixed = getattr(request.app.state, "issuer_codes", None)
    if fixed is not None:
        return fixed()  # type: ignore[no-any-return]
    return {o["issuer_code"] for o in request.app.state.directory.known() if o.get("issuer_code")}


def _unit(line: Any) -> UnitRef:
    return UnitRef(gtin=line.gtin, serial=line.serial, lot=line.lot, expiry=line.expiry)


async def _expected(request: Request, body: NewSession) -> dict[tuple[str, str], UnitRef]:
    store = deps.rw(request)
    if body.kind in ("dispatch", "sell"):
        return {(x.gtin, x.serial): _unit(x) for x in store.stock()}
    if body.kind == "return":
        return {(u.gtin, u.serial): u for u in store.sold()}
    if not body.from_org or not body.source_ref:
        raise Problem(422, "Missing details", "missing_shipment", "Say which shipment you are receiving.")
    if (body.from_org, body.source_ref) in store.received_refs():
        raise Problem(
            409, "Already received", "already_received", "That shipment is already in your records."
        )
    try:
        reply = await request.app.state.share.get(body.from_org, "/share/v1/shipments")
    except SourceUnavailable as e:
        raise Problem(503, "Sender did not answer", "source_unavailable",
                      f"{body.from_org} did not answer ({e.reason}). Try again in a few minutes.") from e  # fmt: skip
    for sh in reply["shipments"]:
        if sh["shipment_id"] == body.source_ref:
            units = [UnitRef.model_validate(u) for u in sh["units"]]
            return {(u.gtin, u.serial): u for u in units}
    raise Problem(
        404,
        "Shipment not found",
        "unknown_shipment",
        f"{body.from_org} has no shipment {body.source_ref} for you.",
    )


@router.post("/sessions")
async def start(body: NewSession, request: Request) -> dict[str, Any]:
    org_type = deps.settings_of(request).org_type
    if body.kind not in ALLOWED.get(org_type, set()):
        raise Problem(
            403, "Not allowed", "wrong_portal", f"A {org_type} portal cannot start a {body.kind} session."
        )
    if body.kind == "dispatch" and not body.to_org:
        raise Problem(422, "Missing details", "missing_party", "Choose who the packs are going to.")
    expected = await _expected(request, body)
    table: SessionTable = request.app.state.scans
    s = table.add(ScanSession(body.kind, expected, issuer_codes(request), to_org=body.to_org,
                              from_org=body.from_org, source_ref=body.source_ref))  # fmt: skip
    return {"session_id": s.session_id, "expected_count": len(expected) if body.kind == "receive" else 0}


@router.post("/sessions/{sid}/read")
def read_code(sid: str, body: ReadBody, request: Request) -> dict[str, Any]:
    s = request.app.state.scans.get(sid)
    row = s.read(body.raw)
    return {"row": row.view(), **s.counts()}


@router.post("/sessions/{sid}/rows/{row_id}/undo")
def undo(sid: str, row_id: int, request: Request) -> dict[str, Any]:
    s = request.app.state.scans.get(sid)
    s.undo(row_id)
    return s.counts()


@router.post("/sessions/{sid}/rows/{row_id}/choose")
def choose(sid: str, row_id: int, body: Choose, request: Request) -> dict[str, Any]:
    s = request.app.state.scans.get(sid)
    return {"row": s.choose(row_id, body.serial).view(), **s.counts()}


@router.get("/sessions/{sid}")
def show(sid: str, request: Request) -> dict[str, Any]:
    s = request.app.state.scans.get(sid)
    return {"kind": s.kind, "rows": [r.view() for r in s.rows if r.status != "removed"], **s.counts(),
            "missing": [u.model_dump(mode="json") for u in s.missing()] if s.kind == "receive" else []}  # fmt: skip


@router.delete("/sessions/{sid}")
def discard(sid: str, request: Request) -> dict[str, str]:
    request.app.state.scans.drop(sid)
    return {"status": "discarded"}


def _hash_phone(last4: str | None, salt: str) -> str | None:
    if last4 is None:
        return None
    if not re.fullmatch(r"\d{4}", last4):
        raise Problem(
            422, "Invalid phone digits", "bad_phone", "Enter the last 4 digits of the phone number."
        )
    return hashlib.sha256(f"{last4}:{salt}".encode()).hexdigest()


@router.post("/sessions/{sid}/finish")
def finish(
    sid: str, body: Finish, request: Request, staff: Session = Depends(current_staff)
) -> dict[str, Any]:
    s = request.app.state.scans.get(sid)
    units = s.units()
    at = deps.effective_at(request, body.at)
    cfg, store = deps.settings_of(request), deps.rw(request)
    try:
        result = _write(request, s.kind, s, units, at, body, staff, cfg, store)
    except ValueError as e:
        raise Problem(409, "Could not record this", "write_refused", str(e)) from e
    for r in s.corrections():
        store.add_scan_correction(ScanCorrection(at=at, raw=r.raw, field="serial", chosen=r.serial or "",
                                                 cost=r.cost or 0.0, confirmed_by=staff.username))  # fmt: skip
    request.app.state.scans.drop(sid)
    request.app.state.activity.add(staff.username, s.kind, f"{len(units)} packs", at)
    return result


def _write(request: Request, kind: str, s: ScanSession, units: list[UnitRef], at: datetime, body: Finish,
           staff: Session, cfg: Any, store: Any) -> dict[str, Any]:  # fmt: skip
    if kind == "dispatch":
        sid = new_id("SHP-" if cfg.org_type == "pharma" else "DSP-")
        if cfg.org_type == "pharma":
            store.record_shipment(
                NewShipment(shipment_id=sid, to_org=s.to_org or "", at=at, units=units, by=staff.username)
            )
        else:
            store.record_dispatch(
                NewDispatch(shipment_id=sid, to_org=s.to_org or "", at=at, units=units, by=staff.username)
            )
        return {"kind": "dispatch", "shipment_id": sid, "to_org": s.to_org, "units": len(units)}
    if kind == "receive":
        store.record_receipt(
            NewReceipt(
                from_org=s.from_org or "",
                source_ref=s.source_ref or "",
                at=at,
                units=units,
                by=staff.username,
            )
        )
        missing = [u.serial for u in s.missing()]
        hook = getattr(request.app.state, "on_discrepancy", None)
        if missing and hook:
            hook(s.from_org, s.source_ref, missing, at)
        return {"kind": "receive", "received": len(units), "missing": missing, "source_ref": s.source_ref}
    if kind == "sell":
        prices = body.prices or {}
        absent = sorted({u.gtin for u in units} - set(prices))
        if absent:
            raise Problem(422, "Missing prices", "missing_price", f"Give a price for product {absent[0]}.")
        bill = body.bill_no or new_id("B-")
        salt = (cfg.shop_settings or {}).get("salt", cfg.org_id)
        store.record_sale(NewSale(bill_no=bill, at=at, customer_ref_hash=_hash_phone(body.customer_last4, salt),
                                  lines=[SaleLine(gtin=u.gtin, serial=u.serial, mrp_paise=prices[u.gtin]) for u in units]))  # fmt: skip
        return {
            "kind": "sell",
            "bill_no": bill,
            "units": len(units),
            "total_paise": sum(prices[u.gtin] for u in units),
        }
    if not body.reason:
        raise Problem(422, "Missing reason", "missing_reason", "Say why the pack came back.")
    for u in units:
        sells = [e for e in store.unit_view(u.gtin, u.serial).events if e.event_type == "sell"]
        store.record_return(
            NewReturn(bill_no=sells[-1].ref or "", gtin=u.gtin, serial=u.serial, reason=body.reason, at=at)
        )
    return {"kind": "return", "units": len(units)}
