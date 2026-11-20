"""Verify one pack: trace, rules, verdict, wording, in the one result shape the interface and tests share (12.5)."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from asali_node.verify.models import DocSignal
from asali_node.verify.rules import reasons as run_rules
from asali_node.verify.trace import Trace, Tracer
from asali_node.verify.verdict import verdict_of
from asali_node.verify.wording import describe

DocsFn = Callable[[Trace], Awaitable[tuple[list[DocSignal], list[dict[str, Any]]]]]
ContextFn = Callable[[Trace], Awaitable[dict[str, Any]]]
ContextDocsFn = Callable[[Trace, dict[str, Any], set[str]], Awaitable[list[dict[str, Any]]]]


async def verify_pack(
    share: Any,
    orgs: list[dict[str, Any]],
    gtin: str,
    serial: str,
    *,
    mode: str,
    read: dict[str, Any] | None = None,
    today: date | None = None,
    documents: DocsFn | None = None,
    context: ContextFn | None = None,
    context_docs: ContextDocsFn | None = None,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    tracer = tracer or Tracer(share, orgs)
    trace = await tracer.run(gtin, serial, today or datetime.now(UTC).astimezone().date())
    # Linked documents and the context run side by side; the context then searches the text for related reading.
    docs_task = asyncio.ensure_future(documents(trace)) if documents else None
    found_context = await context(trace) if context else None
    signals, doc_hits = await docs_task if docs_task else ([], [])
    related = (
        await context_docs(trace, found_context, {d["doc_id"] for d in doc_hits})
        if context_docs and found_context
        else []
    )  # related reading never reaches the rules: only linked documents can
    facts = replace(trace.facts, doc_signals=tuple(signals))
    reasons = run_rules(facts)
    verdict = verdict_of(reasons)
    p, view = facts.product, facts.issuer_view
    return {
        "verdict": verdict,
        **describe(verdict, reasons, facts),
        "reasons": [
            {"code": r.code, "strength": r.strength, "text": r.text, "evidence": list(r.evidence)}
            for r in reasons
        ],
        "pack": {
            "gtin": gtin,
            "serial": serial,
            "lot": facts.lot,
            "expiry": facts.expiry.isoformat() if facts.expiry else None,
            "product": {"brand": p.brand, "generic": p.generic, "strength": p.strength} if p else None,
            "found": bool(view and view.known),
        },  # fmt: skip
        "read": read,
        "history": trace.history,
        "documents": doc_hits,
        "context": found_context,
        "context_documents": related,
        "sources": trace.sources,
        "mode": mode,
        "checked_at": datetime.now(UTC).isoformat(),
    }
