"""Data quality for one organisation's own records: audit, propose, apply (Phase 2)."""

from datetime import datetime
from typing import Any

from asali_codes.candidates import Candidate, serial_candidates
from asali_codes.confusion import weighted_distance
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from asali_node import deps
from asali_node.auth.staff import Session, current_staff
from asali_node.canonical import IST, ScanCorrection
from asali_node.problems import Problem
from asali_node.quality import MAX_FIX_COST, choose, describe, syntax_problems
from asali_node.verify.checks import _existing, _label_facts

router = APIRouter(prefix="/api/quality", dependencies=[Depends(current_staff)])


def _orgs(request: Request) -> list[dict[str, Any]]:
    return list(request.app.state.directory.known())


class FixIn(BaseModel):
    from_serial: str
    to_serial: str


@router.get("")
async def audit(request: Request) -> dict[str, Any]:
    store, orgs = deps.rw(request), _orgs(request)
    issuers = {o["issuer_code"] for o in orgs if o.get("issuer_code")}
    share = request.app.state.share
    recorded = store.recorded_serials()
    syntax = {r["value"]: syntax_problems(r["value"], issuers) for r in recorded}
    well_formed = sorted({v for v, p in syntax.items() if not p})
    issued = await _existing(share, orgs, None, well_formed) if well_formed else set()
    anomalies: list[dict[str, Any]] = []
    for r in recorded:
        problems = list(syntax[r["value"]])
        if not problems and r["value"] not in issued:
            problems.append("no maker has issued this code")
        if not problems:
            continue
        cands = [c for c in serial_candidates(r["value"].upper(), issuers, max_cost=MAX_FIX_COST)]
        real = await _existing(share, orgs, None, [c.value for c in cands]) if cands else set()
        cands = [c for c in cands if c.value in real]
        facts = await _label_facts(share, orgs, [c.value for c in cands]) if cands else {}
        lot = r.get("lot")
        fits = {
            c.value: (None if not lot or facts.get(c.value, (None,))[0] is None else facts[c.value][0] == lot)
            for c in cands
        }
        agreeing = [c for c in cands if fits[c.value] is not False]
        pool: list[Candidate] = agreeing if agreeing and len(agreeing) < len(cands) else cands
        pick = choose(pool)
        anomalies.append({
            "table": r["table"], "column": r["column"], "value": r["value"], "rows": r["rows"], "lot": lot, "problems": problems,
            "candidates": [describe(c, fits[c.value]) for c in cands[:5]],
            "proposal": describe(pick, fits[pick.value]) if pick else None,
        })  # fmt: skip
    return {"org_id": deps.settings_of(request).org_id, "checked": len(recorded), "anomalies": anomalies}


@router.post("/apply")
async def apply(body: FixIn, request: Request, staff: Session = Depends(current_staff)) -> dict[str, Any]:
    store, orgs = deps.rw(request), _orgs(request)
    old, new = body.from_serial.strip().upper(), body.to_serial.strip().upper()
    issuers = {o["issuer_code"] for o in orgs if o.get("issuer_code")}
    if syntax_problems(new, issuers):
        raise Problem(409, "Not a code", "not_a_code", "The replacement is not a well-formed code.")
    if new not in await _existing(request.app.state.share, orgs, None, [new]):
        raise Problem(
            409,
            "Not issued",
            "not_issued",
            "No maker has issued the replacement code, so it cannot replace a record.",
        )
    cost = weighted_distance(new, old)
    if cost > MAX_FIX_COST:
        raise Problem(
            409,
            "Too different",
            "too_different",
            "The replacement is too far from what was recorded to be a correction.",
        )
    changed = store.rename_serial(old, new)
    if changed == 0:
        raise Problem(404, "Not recorded", "not_recorded", "This organisation has no record with that code.")
    store.add_scan_correction(
        ScanCorrection(
            at=datetime.now(IST), raw=old, field="serial", chosen=new, cost=cost, confirmed_by=staff.username
        )
    )
    return {"from_serial": old, "to_serial": new, "rows_changed": changed, "cost": cost}
