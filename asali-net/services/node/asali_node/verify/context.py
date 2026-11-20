"""The asking node's part of Phase 3: ask each organisation for context, merge it, and search the text with it.

Each organisation explores its own database (`context/`, run behind `/share/v1/context`) and returns terms.
Here the terms are merged into one context for the question, and that context is used to search the text
vaults for documents the ML linking did not tie to the pack. A document found this way is shown as related
reading. It never becomes a reason and never changes a verdict: only linked documents do (PLAN.md 12.4).
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

from asali_node.context.aggregate import aggregate
from asali_node.verify.documents import LABELS, vault_orgs
from asali_node.verify.trace import Trace

# What the question "is this pack genuine and safe?" is about. A term that matches one of these is boosted.
INTENT_WORDS = ["recall", "quality", "standard", "cold chain", "temperature", "expiry", "complaint", "counterfeit",
                "fake", "contamination", "storage", "dissolution", "deviation"]  # fmt: skip
MAX_CONTEXT_TERMS, MIN_MATCHED, MAX_CONTEXT_DOCS, SEARCH_LIMIT = 10, 2, 5, 40


def question_words(trace: Trace) -> list[str]:
    words = list(INTENT_WORDS)
    p = trace.facts.product
    if p:
        words += [p.brand, p.generic]
    return words


async def gather_context(
    share: Any, orgs: list[dict[str, Any]], trace: Trace, budget_s: float = 3.0
) -> dict[str, Any]:
    f = trace.facts
    targets = vault_orgs(trace, orgs)
    params = {"gtin": f.gtin, "serial": f.serial, "lot": f.lot or "", "kw": ",".join(question_words(trace))}
    params = {k: v for k, v in params.items() if v}
    tasks = {o: asyncio.create_task(share.get(o, "/share/v1/context", params)) for o in targets}
    if tasks:
        await asyncio.wait(tasks.values(), timeout=budget_s)
    per_org: dict[str, dict[str, Any]] = {}
    summary: list[dict[str, Any]] = []
    for org, task in tasks.items():
        if not task.done() or task.cancelled() or task.exception() is not None:
            task.cancel()
            why = "no answer in time" if not task.done() else "unreachable"
            summary.append({"org_id": org, "name": f.names.get(org, org), "status": "unreachable", "reason": why,
                            "explored_tables": [], "joins": [], "stop_reason": "", "terms": 0, "engine": None})  # fmt: skip
            continue
        body = task.result()
        per_org[org] = body
        summary.append({"org_id": org, "name": f.names.get(org, org), "status": "answered", "reason": "",
                        "explored_tables": body.get("explored_tables", []),
                        "joins": [j["fk"] for j in body.get("joins_performed", [])],
                        "stop_reason": body.get("stop_reason", ""), "terms": len(body.get("ranked_context", [])),
                        "engine": body.get("engine")})  # fmt: skip
    anchors = [a for a in (f.lot, f.serial, f.gtin) if a]
    merged = aggregate(per_org, anchors=anchors)
    return {**merged, "organisations": summary, "question_words": question_words(trace)}


def _search_word(term: dict[str, Any]) -> str | None:
    """The word a context term stands for in running text, or None for terms that are not words (numbers, months)."""
    kind, text = term.get("kind"), str(term["term"])
    if kind == "numeric" or kind == "date":
        return None
    if kind == "categorical" and "=" in text:
        text = text.split("=", 1)[1]
    text = text.strip().lower()
    return text if len(text) >= 3 and re.search(r"[a-z]", text) else None


async def context_documents(
    share: Any, orgs: list[dict[str, Any]], trace: Trace, context: dict[str, Any], linked_ids: set[str],
    budget_s: float = 3.0,
) -> list[dict[str, Any]]:  # fmt: skip
    chosen: list[tuple[str, float]] = []
    for t in context.get("terms", []):
        w = _search_word(t)
        if w and w not in {c[0] for c in chosen}:
            chosen.append((w, float(t["score"])))
        if len(chosen) >= MAX_CONTEXT_TERMS:
            break
    if not chosen:
        return []
    targets = vault_orgs(trace, orgs)
    params = {"q": " ".join(w for w, _ in chosen), "limit": SEARCH_LIMIT}
    tasks = {o: asyncio.create_task(share.get(o, "/share/v1/documents/search", params)) for o in targets}
    await asyncio.wait(tasks.values(), timeout=budget_s)
    total = sum(s for _, s in chosen) or 1.0
    names, found = trace.facts.names, []
    for org, task in tasks.items():
        if not task.done() or task.cancelled() or task.exception() is not None:
            task.cancel()
            continue
        for hit in task.result().get("hits", []):
            if f"{org}:{hit['id']}" in linked_ids:
                continue
            text = f"{hit.get('title', '')} {hit['body']}".lower()
            matched = [(w, s) for w, s in chosen if re.search(r"\b" + re.escape(w), text)]
            if len(matched) < MIN_MATCHED:
                continue
            found.append((sum(s for _, s in matched) / total, org, hit, [w for w, _ in matched]))
    found.sort(key=lambda r: (-r[0], -r[2]["created_at"]))
    out = []
    for score, org, hit, matched in found[:MAX_CONTEXT_DOCS]:
        out.append({
            "doc_id": f"{org}:{hit['id']}", "org_id": org, "org_name": names.get(org, org), "doc_type": hit["doc_type"],
            "kind": hit["kind"], "title": hit["title"],
            "created_at": datetime.fromtimestamp(hit["created_at"], UTC).isoformat(),
            "snippet": {"text": hit["body"].strip()[:240]}, "linked_to": [], "claims": [],
            "issue_labels": hit.get("issue_labels", []), "label": LABELS[hit["kind"]],
            "matched_terms": matched, "context_score": round(score, 3), "found_by": "context",
        })  # fmt: skip
    return out
