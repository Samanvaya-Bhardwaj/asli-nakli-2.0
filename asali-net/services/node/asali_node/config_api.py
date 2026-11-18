"""What the portal needs to build itself for this organisation. Never secrets or storage addresses."""

from typing import Any

from fastapi import APIRouter, Request

from asali_node.settings import Settings

router = APIRouter()


def public_config(s: Settings) -> dict[str, Any]:
    return {
        "org_id": s.org_id,
        "org_type": s.org_type,
        "name": s.org_name,
        "city": s.org_city,
        "state": s.org_state,
        "issuer_code": s.issuer_code,
        "gs1_prefix": s.gs1_prefix,
        "mode": s.asali_mode,
        "host_name": s.host_name,
        "shop": s.shop_settings if s.org_type == "shop" else None,
    }


@router.get("/api/config")
def config(request: Request) -> dict[str, Any]:
    return public_config(request.app.state.settings)
