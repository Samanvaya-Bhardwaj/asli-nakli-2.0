"""Share API, query context (Phase 3). The node explores its own database through its own keys and returns terms.

It returns terms, never rows: a caller learns what is related to the pack (a recall reason, a storage note, a
city) with the table, column and join path it came from, and not another organisation's records.
"""

from typing import Any

from fastapi import APIRouter, Request

from asali_node import deps
from asali_node.problems import Problem

router = APIRouter(prefix="/share/v1")
MAX_KEYWORDS = 30


@router.get("/context")
def context(
    request: Request, gtin: str | None = None, serial: str | None = None, lot: str | None = None, kw: str = ""
) -> dict[str, Any]:
    if not (gtin or serial or lot):
        raise Problem(400, "Nothing to look up", "no_key", "Give a pack code, a product number or a batch.")
    store = deps.ro(request)
    if not hasattr(store, "context_for"):
        return {
            "ranked_context": [],
            "explored_tables": [],
            "stop_reason": "this node does not discover context",
        }
    keywords = [k for k in kw.split(",") if k][:MAX_KEYWORDS]
    out: dict[str, Any] = store.context_for(gtin, serial, lot, keywords)
    return {**out, "org_id": deps.settings_of(request).org_id, "engine": deps.settings_of(request).engine}
