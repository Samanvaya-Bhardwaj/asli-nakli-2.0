"""Read-only share API, common routes (more arrive in M4)."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from asali_node.settings import Settings

router = APIRouter(prefix="/share/v1")


def served_by(s: Settings) -> dict[str, str]:
    return {"org_id": s.org_id, "host_name": s.host_name, "at": datetime.now(UTC).isoformat()}


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "org_id": request.app.state.settings.org_id}


@router.get("/org")
def org(request: Request) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    return {
        "org_id": s.org_id,
        "org_type": s.org_type,
        "name": s.org_name,
        "city": s.org_city,
        "state": s.org_state,
        "issuer_code": s.issuer_code,
        "gs1_prefix": s.gs1_prefix,
        "base_url": s.public_base_url,
        "host_name": s.host_name,
        "engine": s.engine,
        "vault": "meilisearch" if s.meili_url else None,
        "served_by": served_by(s),
    }
