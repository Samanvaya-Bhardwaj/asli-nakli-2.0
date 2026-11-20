"""Find the documents about a pack in every relevant vault, check their claims, rank them (TEXT_ML.md 7)."""

import asyncio
import math
from datetime import UTC, datetime
from typing import Any

from asali_node.network.client import SourceUnavailable
from asali_node.verify.models import DocSignal
from asali_node.verify.text_checks import ClaimResult, signals_for
from asali_node.verify.trace import Trace

KIND_WEIGHT = {"official": 1.0, "operational": 0.8, "allegation": 0.6}
LABELS = {
    "allegation": "Reported by a customer, not verified",
    "operational": "Record kept by an organisation on the route",
    "official": "Official notice",
}
MAX_HITS, MAX_PER_TYPE, LIMIT_PER_VAULT = 10, 4, 20
SPECIFIC = {"unit": 3, "batch": 2, "shipment": 2, "org": 1, "product": 1}


def context_keys(trace: Trace) -> list[str]:
    f = trace.facts
    keys = [f"unit:{f.gtin}/{f.serial}", f"product:{f.gtin}"]
    if f.lot:
        keys.append(f"batch:{f.gtin}/{f.lot}")
    for h in f.chain:
        for e in h.view.events if h.view else []:
            if e.event_type == "ship" and e.ref:
                keys.append(f"shipment:{e.org_id}/{e.ref}")
    return keys


def vault_orgs(trace: Trace, orgs: list[dict[str, Any]]) -> list[str]:
    route = [h.org_id for h in trace.facts.chain]
    extra = [o["org_id"] for o in orgs if o["org_type"] in ("regulator", "consumer")]
    return list(dict.fromkeys([*route, *extra]))[:8]


async def retrieve(
    share: Any, orgs: list[dict[str, Any]], trace: Trace, budget_s: float = 3.0
) -> tuple[list[DocSignal], list[dict[str, Any]]]:
    f = trace.facts
    if not f.chain or f.chain[0].view is None or not f.chain[0].view.known:
        return [], []
    keys = context_keys(trace)
    targets = vault_orgs(trace, orgs)
    params = {"link_keys": ",".join(keys), "limit": LIMIT_PER_VAULT}
    tasks = [asyncio.create_task(share.get(o, "/share/v1/documents/search", params)) for o in targets]
    await asyncio.wait(tasks, timeout=budget_s) if tasks else None
    maker = f.chain[0].org_id
    now = datetime.now(UTC)
    ranked: list[tuple[float, dict[str, Any], list[DocSignal], list[ClaimResult]]] = []
    for org, task in zip(targets, tasks, strict=True):
        if not task.done() or task.cancelled() or task.exception() is not None:
            task.cancel()
            continue
        for hit in task.result().get("hits", []):
            links = [x for x in hit["links"] if x["entity_key"] in keys and x["confidence"] >= 0.6]
            if not links:
                continue
            best = max(
                links, key=lambda x: (SPECIFIC.get(x["entity_key"].split(":")[0], 0), x["confidence"])
            )  # the most specific link
            age = max(0.0, (now.timestamp() - hit["created_at"]) / 86400)
            sigs, checks = signals_for(hit, f, best["confidence"], maker, best["entity_key"])
            score = best["confidence"] * KIND_WEIGHT[hit["kind"]] * math.exp(-age / 365)
            if sigs:  # a document that changed the verdict is always shown to the person
                score += 10
            ranked.append((score, {**hit, "_best": best, "_org": org}, sigs, checks))
    ranked.sort(key=lambda r: -r[0])
    chosen, per_type, seen = [], {}, set()
    for _score, hit, sigs, checks in ranked:
        if hit["id"] in seen or per_type.get(hit["doc_type"], 0) >= MAX_PER_TYPE or len(chosen) >= MAX_HITS:
            continue
        seen.add(hit["id"])
        per_type[hit["doc_type"]] = per_type.get(hit["doc_type"], 0) + 1
        chosen.append((hit, sigs, checks))
    first_seen: dict[str, list[DocSignal]] = {}
    for _score, hit, sigs, _checks in ranked:
        first_seen.setdefault(hit["id"], sigs)
    signals = [s for sigs in first_seen.values() for s in sigs]
    return signals, [_dochit(h, checks, trace) for h, _, checks in chosen]


def _dochit(hit: dict[str, Any], checks: list[ClaimResult], trace: Trace) -> dict[str, Any]:
    names = trace.facts.names
    return {
        "doc_id": f"{hit['_org']}:{hit['id']}", "org_id": hit["_org"], "org_name": names.get(hit["_org"], hit["_org"]),
        "doc_type": hit["doc_type"], "kind": hit["kind"], "title": hit["title"],
        "created_at": datetime.fromtimestamp(hit["created_at"], UTC).isoformat(),
        "snippet": {"text": hit["body"].strip()[:240]},
        "linked_to": [{"entity": hit["_best"]["entity_key"], "confidence": hit["_best"]["confidence"], "because": hit["_best"].get("because", [])}],
        "claims": [{"name": c.name, "value": c.value, "check": c.check, "against": c.against} for c in checks],
        "issue_labels": hit.get("issue_labels", []), "label": LABELS[hit["kind"]],
    }  # fmt: skip


_ = SourceUnavailable
