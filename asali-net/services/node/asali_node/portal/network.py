"""The network page: every organisation, its computer, whether it answers, how fast, and what storage it uses."""

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Request

from asali_node.network.client import SourceUnavailable

router = APIRouter(prefix="/api")
CACHE_S = 10.0


async def _probe(share: Any, org: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    row = {k: org.get(k) for k in ("org_id", "org_type", "name", "city", "state", "host_name", "last_seen")}
    try:
        info = await share.get(org["org_id"], "/share/v1/org")
        row |= {
            "online": True,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "engine": info.get("engine"),
            "vault": info.get("vault"),
        }
    except SourceUnavailable as e:
        row |= {"online": False, "latency_ms": None, "engine": None, "vault": None, "reason": e.reason}
    return row


@router.get("/network")
async def network(request: Request) -> dict[str, Any]:
    state = request.app.state
    cached = getattr(state, "network_cache", None)
    if cached and time.monotonic() - cached[0] < CACHE_S:
        return dict(cached[1])
    orgs = sorted(state.directory.known(), key=lambda o: (o["org_type"], o["org_id"]))
    rows = await asyncio.gather(*[_probe(state.share, o) for o in orgs])
    body = {"orgs": list(rows), "online": sum(r["online"] for r in rows), "total": len(rows), "mode": state.settings.asali_mode,
            "self": state.settings.org_id, "directory_stale": getattr(state.directory, "stale_since", None)}  # fmt: skip
    state.network_cache = (time.monotonic(), body)
    return body
