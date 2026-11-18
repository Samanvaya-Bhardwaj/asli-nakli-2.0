"""Read-only share API, common routes. Only the health check so far; the rest arrives in M4."""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/share/v1")


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "org_id": request.app.state.settings.org_id}
