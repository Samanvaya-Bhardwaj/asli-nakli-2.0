"""Consumer portal: problem reports. (/api/check arrives with verification, M6.) No sign-in needed."""

import asyncio
import hashlib
import json
from datetime import date, datetime
from typing import Any

from asali_codes.read import format_serial
from asali_text.clean import normalise, redact
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from asali_node import deps
from asali_node.canonical import NewCheck, NewReport
from asali_node.problems import Problem
from asali_node.stores.sqlbase import new_id
from asali_node.verify.checks import PLACEHOLDER_GTIN, Resolution, resolve_input
from asali_node.verify.context import context_documents, gather_context
from asali_node.verify.documents import retrieve
from asali_node.verify.engine import verify_pack
from asali_node.verify.trace import Tracer

router = APIRouter(prefix="/api")


class ReportIn(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    city: str = Field(min_length=2)
    check_id: str | None = None
    gtin: str | None = None
    serial: str | None = None
    purchase_date: date | None = None
    shop_name: str | None = None
    at: datetime | None = None


@router.post("/report", status_code=201)
def report(body: ReportIn, request: Request) -> dict[str, Any]:
    clean, removed = redact(normalise(body.text))
    if len(clean.replace("[phone]", "").replace("[email]", "").strip()) < 10:
        raise Problem(
            422, "Report too short", "too_short", "Say what is wrong with the pack or the medicine."
        )
    at = deps.effective_at(request, body.at)
    doc_id = new_id("doc_")
    sink = request.app.state.documents  # the text service when it exists, otherwise a plain file store
    sink.add(doc_id, "consumer_complaint", clean, {"city": body.city, "gtin": body.gtin, "serial": body.serial,
                                                   "purchase_date": body.purchase_date.isoformat() if body.purchase_date else None,
                                                   "shop_name": body.shop_name, "at": at.isoformat()})  # fmt: skip
    report_id = deps.rw(request).record_report(
        NewReport(
            check_id=body.check_id, doc_id=doc_id, gtin=body.gtin, serial=body.serial, city=body.city, at=at
        )
    )
    return {"report_id": report_id, "doc_id": doc_id, "removed": removed}


# ---- checking a pack ----
class CheckIn(BaseModel):
    raw: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=2)
    at: datetime | None = None


class ConfirmIn(BaseModel):
    check_id: str
    serial: str


def _device(request: Request) -> str:
    who = f"{request.client.host if request.client else ''}|{request.headers.get('user-agent', '')}"
    return hashlib.sha256(f"{deps.settings_of(request).org_id}:{who}".encode()).hexdigest()[:16]


def _orgs(request: Request) -> list[dict[str, Any]]:
    return list(request.app.state.directory.known())


def _pipelines(request: Request, orgs: list[dict[str, Any]]) -> dict[str, Any]:
    """The text and context steps every verification runs after the trace."""
    share = request.app.state.share
    return {
        "documents": lambda trace: retrieve(share, orgs, trace),
        "context": lambda trace: gather_context(share, orgs, trace),
        "context_docs": lambda trace, ctx, linked: context_documents(share, orgs, trace, ctx, linked),
    }


async def verify_resolved(
    request: Request, res: Resolution, record: bool, city: str = "", at: datetime | None = None
) -> dict[str, Any]:
    result = await verify_pack(request.app.state.share, _orgs(request), res.gtin or PLACEHOLDER_GTIN, res.serial or "",
                               mode=deps.settings_of(request).asali_mode, read=res.read,
                               **_pipelines(request, _orgs(request)))  # fmt: skip
    if result["pack"]["gtin"] == PLACEHOLDER_GTIN:
        result["pack"]["gtin"] = None
    if record:
        deps.rw(request).record_check(NewCheck(
            raw_input=res.read.get("raw", ""), gtin=res.gtin, serial=res.serial, verdict=result["verdict"],
            reasons=[r["code"] for r in result["reasons"]], city=city, at=deps.effective_at(request, at),
            device_hash=_device(request)))  # fmt: skip
    return result


def _question(request: Request, res: Resolution, city: str, at: datetime | None) -> dict[str, Any]:
    check_id = new_id("pending_")
    request.app.state.pending[check_id] = (res, city, at)
    body: dict[str, Any] = {
        "status": res.decision,
        "message": res.message,
        "read": res.read,
        "choices": res.choices,
    }
    if res.decision == "needs_confirmation":
        body |= {"check_id": check_id, "serial": res.serial, "serial_shown": format_serial(res.serial or "")}
    return body


@router.post("/check")
async def check(body: CheckIn, request: Request) -> dict[str, Any]:
    res = await resolve_input(body.raw, request.app.state.share, _orgs(request))
    if res.decision != "verify":
        return _question(request, res, body.city, body.at)
    return {"status": "done", "result": await verify_resolved(request, res, True, body.city, body.at)}


@router.post("/check/confirm")
async def confirm(body: ConfirmIn, request: Request) -> dict[str, Any]:
    pending = request.app.state.pending.pop(body.check_id, None)
    if pending is None or pending[0].serial != body.serial:
        raise Problem(
            404, "Not found", "unknown_check", "That check is no longer waiting. Scan or type the code again."
        )
    res, city, at = pending
    res.read["confirmed"] = True
    return {"status": "done", "result": await verify_resolved(request, res, True, city, at)}


@router.get("/verify/stream")
async def stream(request: Request, raw: str, city: str = "Unknown") -> StreamingResponse:
    """Server-sent events: `progress` while organisations answer, then `result` (or the question to confirm)."""

    async def events() -> Any:
        orgs = _orgs(request)
        res = await resolve_input(raw, request.app.state.share, orgs)
        if res.decision != "verify":
            yield sse("result", _question(request, res, city, None))
            return
        total = 1 + sum(o["org_type"] in ("regulator", "shop", "consumer") for o in orgs)
        tracer = Tracer(request.app.state.share, orgs)
        task = asyncio.create_task(verify_pack(request.app.state.share, orgs, res.gtin or PLACEHOLDER_GTIN, res.serial or "",
                                               mode=deps.settings_of(request).asali_mode, read=res.read, tracer=tracer,
                                               **_pipelines(request, orgs)))  # fmt: skip
        while not task.done():
            yield sse(
                "progress",
                {
                    "asked": len(tracer.sources),
                    "answered": sum(s["status"] == "answered" for s in tracer.sources.values()),
                    "total": total,
                },
            )
            await asyncio.sleep(0.15)
        result = task.result()
        deps.rw(request).record_check(NewCheck(raw_input=raw, gtin=res.gtin, serial=res.serial, verdict=result["verdict"],
                                               reasons=[r["code"] for r in result["reasons"]], city=city,
                                               at=deps.effective_at(request, None), device_hash=_device(request)))  # fmt: skip
        yield sse("result", {"status": "done", "result": result})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
