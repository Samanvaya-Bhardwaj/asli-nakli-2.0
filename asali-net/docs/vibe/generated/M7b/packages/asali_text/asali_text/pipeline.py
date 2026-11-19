"""Ingest one document: clean, type, mentions, links, claims, issue labels (TEXT_ML.md 4)."""

from datetime import datetime
from typing import Any

from asali_text.claims import KIND, extract_claims
from asali_text.clean import normalise, redact
from asali_text.gazetteer import Gazetteer
from asali_text.language import language_of
from asali_text.link import LINKED, POSSIBLE, DocFacts, because, featurize_all
from asali_text.mentions import extract
from asali_text.models import Models
from asali_text.world import World

COMPLAINT_TYPES = {"consumer_complaint", "counter_note"}
TITLES = {
    "coa": "Certificate of analysis", "batch_release_note": "Batch release note", "deviation_report": "Deviation report",
    "recall_notice": "Recall notice", "temperature_report": "Temperature report", "delivery_note": "Delivery note",
    "discrepancy_note": "Discrepancy note", "damage_report": "Damage report", "counter_note": "Counter note",
    "return_note": "Return note", "consumer_complaint": "Customer complaint", "nsq_alert": "Not of standard quality list",
    "ban_order": "Ban order", "inspection_report": "Inspection report",
}  # fmt: skip


def _link_records(doc: DocFacts, world: World, models: Models) -> list[dict[str, Any]]:
    cands, x = featurize_all(doc, world)
    out = []
    for c, p in zip(cands, models.link.proba(x), strict=True):
        if p >= POSSIBLE:
            out.append({"entity_key": c.key, "entity_type": c.entity_type, "confidence": round(float(p), 4),
                        "because": because(c), "state": "linked" if p >= LINKED else "possible", "implied": False,
                        "_entity": c.entity})  # fmt: skip
    return out


def _implied(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A link to a pack counts for its batch and product; a link to a batch counts for its product."""
    have = {link["entity_key"] for link in links}
    extra = []
    for link in links:
        e = link.get("_entity")
        implied = []
        if link["entity_type"] == "unit":
            implied = [("batch", f"batch:{e.gtin}/{e.lot}"), ("product", f"product:{e.gtin}")]
        elif link["entity_type"] == "batch":
            implied = [("product", f"product:{e.gtin}")]
        for kind, key in implied:
            if key not in have:
                have.add(key)
                extra.append(
                    {
                        **link,
                        "entity_key": key,
                        "entity_type": kind,
                        "because": ["implied by a more specific link"],
                        "implied": True,
                    }
                )
    return [*links, *extra]


def ingest(text: str, *, owner_org: str, declared_type: str | None, world: World, gaz: Gazetteer, models: Models,
           now: datetime, doc_id: str, title: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:  # fmt: skip
    body, removed = redact(normalise(text))
    predicted = models.type.predict(body)
    doc_type = declared_type or predicted["doc_type"]
    mismatch = bool(
        declared_type and predicted["doc_type"] != declared_type and predicted["confidence"] >= 0.8
    )
    mentions = extract(body, gaz, now.year)
    facts = DocFacts(owner_org, doc_type, mentions, now.year)
    links = _implied(_link_records(facts, world, models))
    doc = {
        "id": doc_id, "org_id": owner_org, "doc_type": doc_type, "doc_type_declared": declared_type,
        "kind": KIND.get(doc_type, "operational"), "title": title or f"{TITLES.get(doc_type, doc_type)}, {now.day} {now:%b %Y}",
        "body": body, "language": language_of(body), "created_at": int(now.timestamp()),
        "issue_labels": models.issue.predict(body) if doc_type in COMPLAINT_TYPES else [],
        "mentions": {k: [m.as_dict() for m in mentions if m.kind == k] for k in sorted({m.kind for m in mentions})},
        "claims": extract_claims(doc_type, body, mentions), "meta": meta or {}, "type_confidence": predicted["confidence"],
    }  # fmt: skip
    for link in links:
        link.pop("_entity", None)
    return {
        "doc": doc,
        "links": links,
        "type_mismatch": mismatch,
        "predicted_type": predicted,
        "removed": removed,
    }
