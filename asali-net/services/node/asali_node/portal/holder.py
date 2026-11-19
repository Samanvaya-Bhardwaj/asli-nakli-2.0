"""Distributor and shop portals: what is incoming, what is in stock, who to send to, local alerts."""

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Request

from asali_node import deps
from asali_node.auth.staff import current_staff
from asali_node.network.client import SourceUnavailable
from asali_node.problems import Problem

router = APIRouter(prefix="/api", dependencies=[Depends(current_staff)])
UPSTREAM = {"distributor": "pharma", "shop": "distributor"}
BUDGET_S = 6.0


def _sources(results: list[Any], orgs: list[str]) -> list[dict[str, str]]:
    return [
        {"org_id": o, "status": "unreachable" if isinstance(r, SourceUnavailable) else "answered",
         "reason": r.reason if isinstance(r, SourceUnavailable) else ""}
        for o, r in zip(orgs, results, strict=True)
    ]  # fmt: skip


@router.get("/incoming")
async def incoming(request: Request) -> dict[str, Any]:
    """Shipments addressed to this organisation that it has not received yet, from every upstream node."""
    cfg, store = deps.settings_of(request), deps.rw(request)
    upstream = [
        o["org_id"] for o in request.app.state.directory.known() if o["org_type"] == UPSTREAM[cfg.org_type]
    ]
    results = await request.app.state.share.gather(
        [(o, "/share/v1/shipments", None) for o in upstream], BUDGET_S
    )
    done, out = store.received_refs(), []
    for org, r in zip(upstream, results, strict=True):
        if isinstance(r, SourceUnavailable):
            continue
        for sh in r["shipments"]:
            if (org, sh["shipment_id"]) not in done:
                out.append(
                    {
                        "from_org": org,
                        "shipment_id": sh["shipment_id"],
                        "at": sh["at"],
                        "count": len(sh["units"]),
                    }
                )
    out.sort(key=lambda x: x["at"], reverse=True)
    return {"incoming": out, "sources": _sources(results, upstream)}


@router.get("/stock")
def stock(request: Request) -> dict[str, Any]:
    """Own stock, grouped by product and lot."""
    groups: dict[tuple[str, str | None, str | None], int] = defaultdict(int)
    for s in deps.rw(request).stock():
        groups[(s.gtin, s.lot, s.expiry.isoformat() if s.expiry else None)] += 1
    rows = [
        {"gtin": g, "lot": lot, "expiry": exp, "count": n}
        for (g, lot, exp), n in sorted(groups.items(), key=str)
    ]
    return {"total": sum(r["count"] for r in rows), "groups": rows}


@router.get("/parties")
def parties(request: Request, type: str | None = None) -> dict[str, Any]:
    """Organisations this portal can send to or receive from, with served states first for a distributor."""
    cfg = deps.settings_of(request)
    served = set(json.loads(cfg.served_states)) if cfg.served_states else set()
    rows = [o for o in request.app.state.directory.known() if type is None or o["org_type"] == type]
    rows.sort(key=lambda o: (o["state"] not in served, not o.get("online", False), o["org_id"]))
    keep = ("org_id", "org_type", "name", "city", "state", "host_name", "base_url")
    return {"parties": [{k: o[k] for k in keep} | {"serves_here": o["state"] in served} for o in rows]}


@router.get("/alerts")
async def alerts(request: Request) -> dict[str, Any]:
    """Regulator alerts for this shop's state plus national ones, newest first."""
    cfg = deps.settings_of(request)
    if cfg.org_type != "shop":
        raise Problem(404, "Not found", "not_served", "Only shops show local alerts.")
    regs = [o["org_id"] for o in request.app.state.directory.known() if o["org_type"] == "regulator"]
    results = await request.app.state.share.gather(
        [(o, "/share/v1/alerts", {"state": cfg.org_state}) for o in regs], BUDGET_S
    )
    found = [a for r in results if not isinstance(r, SourceUnavailable) for a in r["alerts"]]
    found.sort(key=lambda a: a["issued_at"], reverse=True)
    return {"alerts": found, "sources": _sources(results, regs)}
