"""Simulation-only helper: ask another node's share API through this node's signed client."""

from typing import Any

from fastapi import APIRouter, Query, Request

from asali_node.network.client import SourceUnavailable
from asali_node.problems import Problem

router = APIRouter()


@router.get("/api/debug/ask")
async def ask(request: Request, org: str, path: str = Query(pattern=r"^/share/v1/")) -> dict[str, Any]:
    if request.app.state.settings.asali_mode != "simulation":
        raise Problem(404, "Not found", "http_error")
    try:
        result: dict[str, Any] = await request.app.state.share.get(org, path)
    except SourceUnavailable as e:
        raise Problem(502, f"{e.org_id} did not answer", e.reason) from None
    return result
