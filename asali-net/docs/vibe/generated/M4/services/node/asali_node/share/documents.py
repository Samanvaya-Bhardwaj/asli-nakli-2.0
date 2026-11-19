"""Share API, text documents. Empty until the text pipeline (M7) fills this node's vault."""

from typing import Any

from fastapi import APIRouter, Request

from asali_node.problems import Problem

router = APIRouter(prefix="/share/v1")


@router.get("/documents/search")
def search(request: Request) -> dict[str, Any]:
    service = getattr(request.app.state, "text", None)
    if service is None:
        return {"hits": [], "searched": False}
    return {"hits": service.search(dict(request.query_params)), "searched": True}


@router.get("/documents/{doc_id}")
def document(request: Request, doc_id: str) -> dict[str, Any]:
    service = getattr(request.app.state, "text", None)
    doc = service.get(doc_id) if service else None
    if doc is None:
        raise Problem(
            404, "Not found", "unknown_document", "This organisation holds no document with that id."
        )
    return dict(doc)
