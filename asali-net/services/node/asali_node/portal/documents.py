"""Staff documents: paste or upload text, see what the pipeline found, reject a wrong link (PLAN.md 11, TEXT_ML.md 6.3)."""

from datetime import datetime
from typing import Any

from asali_text.claims import DOC_TYPES
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from asali_node import deps
from asali_node.auth.staff import Session, current_staff
from asali_node.problems import Problem

router = APIRouter(prefix="/api/documents", dependencies=[Depends(current_staff)])


class DocumentIn(BaseModel):
    text: str = Field(min_length=10, max_length=60000)
    declared_type: str | None = None
    title: str | None = None
    at: datetime | None = None


def _service(request: Request) -> Any:
    svc = getattr(request.app.state, "text", None)
    if svc is None:
        raise Problem(
            503,
            "Documents are off",
            "no_text_service",
            "This node has no trained text models, so it cannot read documents.",
        )
    return svc


@router.post("", status_code=201)
async def add_document(
    body: DocumentIn, request: Request, staff: Session = Depends(current_staff)
) -> dict[str, Any]:
    if body.declared_type and body.declared_type not in DOC_TYPES:
        raise Problem(422, "Unknown document type", "bad_type", f"Choose one of: {', '.join(DOC_TYPES)}.")
    at = deps.effective_at(request, body.at)
    res = await _service(request).ingest(body.text, declared_type=body.declared_type, title=body.title, at=at,
                                         meta={"by": staff.username}, keep_original=True)  # fmt: skip
    pred = res["predicted_type"]
    note = (
        f"This looks like {pred['doc_type'].replace('_', ' ')}. You chose {body.declared_type.replace('_', ' ')}."
        if res["type_mismatch"] and body.declared_type
        else ""
    )
    request.app.state.activity.add(staff.username, "document", res["doc"]["title"], at)
    return {"doc_id": res["doc"]["id"], "doc_type": res["doc"]["doc_type"], "type_confidence": pred["confidence"], "type_note": note,
            "kind": res["doc"]["kind"], "language": res["doc"]["language"], "links": res["links"], "claims": res["doc"]["claims"],
            "issue_labels": res["doc"]["issue_labels"], "removed": res["removed"]}  # fmt: skip


@router.get("")
def list_documents(request: Request, type: str | None = None, linked: bool | None = None) -> dict[str, Any]:
    docs = _service(request).rw.listing(doc_type=type, linked=linked)
    return {
        "documents": [
            {k: d[k] for k in ("id", "doc_type", "kind", "title", "language", "created_at", "issue_labels")}
            | {"links": len(d["links"])}
            for d in docs
        ]
    }


@router.get("/{doc_id}")
def show(doc_id: str, request: Request) -> dict[str, Any]:
    doc = _service(request).rw.get(doc_id)
    if doc is None:
        raise Problem(404, "Not found", "unknown_document", "There is no document with that id here.")
    return dict(doc)


@router.post("/{doc_id}/links/{key:path}/reject")
def reject(doc_id: str, key: str, request: Request) -> dict[str, str]:
    if not _service(request).rw.reject_link(doc_id, key):
        raise Problem(404, "Not found", "unknown_link", "That link does not exist.")
    return {"status": "rejected"}
