"""
retrieval.py
------------
Context-aware retrieval of unstructured documents, and the integrated
structured + unstructured response (Phase 3).

  build_search_request()  turns the SCORE query context into a search request:
                          the question's words, the top context terms (weighted by their
                          aggregated score), the identifiers - the question's own (anchors,
                          weight 1.0) and those the databases discovered through FK joins
                          (weight 0.5) - company / product names from the context, and the
                          question's intents (which document types suit it)
  search_documents()      sends that request to every source's document store (each source
                          keeps and searches its own documents) and merges the ranked results
  integrated_response()   A-H: question, structured results, local contexts, aggregated context,
                          documents, scores, provenance, why each was retrieved - with verified
                          structured facts kept apart from what documents report

Documents never change the ASALI/NAKALI verdict; an unverified complaint is reported
as an allegation, next to what the structured records say.
"""

from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from integration.federation import runtime
from integration.federation.remote import NodeError, client
from integration.uncertainty.standardize import canonical_code

ID_KINDS = [
    ("item_code", re.compile(r"^MED-[A-Z0-9]+-[A-Z0-9]+$")),
    ("dispatch_ref", re.compile(r"^DBATCH-[A-Z]?\d+$")),
    ("batch_number", re.compile(r"^(BATCH-[A-Z]\d{3,4}|[A-Z]{3}\d{5})$")),
    ("manufacturer_id", re.compile(r"^MFG-\d{3}$")),
    ("distributor_id", re.compile(r"^DIST-\d{3}$")),
    ("vendor_id", re.compile(r"^VND-\d{3}$")),
]
NAME_COLUMNS = ("company_name", "product_name", "brand_name", "generic_name", "vendor_name", "site_name", "name")
MAX_CONTEXT_TERMS = 15
MAX_CONTEXT_IDS = 30
TOP_K = 10


def _kind(value: str) -> str:
    v = value.strip().upper()
    for kind, rx in ID_KINDS:
        if rx.match(v):
            return kind
    return ""


def build_search_request(pq, query_context: Dict[str, Any], combined: Dict[str, Any], anchors: List[str]) -> Dict[str, Any]:
    terms = query_context.get("terms", [])
    top = max((t["score"] for t in terms), default=1.0) or 1.0
    entities: Dict[tuple, Dict[str, Any]] = {}

    def add(value, origin, weight, anchor=False):
        k = _kind(str(value))
        if not k:
            return
        v = canonical_code(str(value)) if k == "item_code" else str(value).strip().upper()
        key = (k, v)
        if key not in entities or entities[key]["weight"] < weight:
            entities[key] = {"kind": k, "value": v, "weight": weight, "anchor": anchor, "origin": origin}

    for a in anchors:
        add(a, "the question", 1.0, anchor=True)
    for t in terms[:MAX_CONTEXT_IDS]:
        if t["kind"] == "identifier":
            add(t["term"], f"context from {'/'.join(t['databases'])}", 0.5)
    for link in combined.get("cross_source_links", [])[:20]:
        add(link["value"], f"shared by {'/'.join(link['databases'])}", 0.5)

    context_terms, names = [], []
    for t in terms:
        if t["kind"] == "numeric":
            continue
        key, display = t["key"], t["term"]
        if t["kind"] == "identifier":
            if not _kind(display) and re.search(r"[a-z]", display, re.I) and " " in display.strip():
                names.append(display)              # e.g. a generic name reached through an FK
            continue
        value = display.split("=", 1)[1] if "=" in display else display
        column = key.split(":", 1)[1].split("=", 1)[0] if "=" in key else ""
        if column.split(".")[-1] in NAME_COLUMNS:
            names.append(value)
        if len(context_terms) < MAX_CONTEXT_TERMS:
            context_terms.append({"term": value, "weight": round(0.8 * t["score"] / top, 3),
                                  "from": "/".join(t["databases"])})
    ents = sorted(entities.values(), key=lambda e: (-e["weight"], e["kind"], e["value"]))
    req = {"query_text": pq.text, "context_terms": context_terms, "entities": ents,
           "names": sorted(set(names))[:10], "intents": list(pq.intents), "top_k": TOP_K}
    req["display"] = (f"text: \"{pq.text}\"\n"
                      f"  + context terms: " + ", ".join(f"{c['term']}^{c['weight']}" for c in context_terms) + "\n"
                      f"  + identifiers:   " + ", ".join(f"{e['kind']}={e['value']}^{e['weight']}" for e in ents) + "\n"
                      f"  + names:         " + ", ".join(req["names"]) + "\n"
                      f"  + intents:       " + ", ".join(pq.intents))
    return req


def search_documents(request: Dict[str, Any]) -> Dict[str, Any]:
    body = {k: v for k, v in request.items() if k != "display"}

    def one(d):
        try:
            res = client(d).request("POST", "/api/v3/documents/search", body)
            return d, {"status": "ok", "served_by": res.get("source"), **res["result"]}
        except (NodeError, runtime.ConfigError) as e:
            return d, {"status": getattr(e, "status", "not_configured"), "error": str(e), "results": []}

    with ThreadPoolExecutor(max_workers=4) as pool:
        per_db = dict(pool.map(one, runtime.DB_IDS))
    merged = [r for d in runtime.DB_IDS for r in per_db[d]["results"]]
    merged.sort(key=lambda r: (-r["score"], r["doc_id"]))
    return {"per_database": {d: {k: v for k, v in r.items() if k != "results"} | {"returned": len(r["results"])}
                             for d, r in per_db.items()},
            "documents": merged[:request.get("top_k", TOP_K)]}


# -- integration -------------------------------------------------------------------------------

def _structured_facts(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Statements the databases establish, each with the record that establishes it."""
    facts = []
    for v in result.get("verdicts", []):
        if v["status"] == "COMPUTED":
            facts.append({"fact": f"{v['item_code']}: verdict {v['verdict']} (trust {v['trust_score']}"
                                  + (f", vetoes {', '.join(v['veto_codes'])}" if v["veto_codes"] else "") + ")",
                          "source": "Phase 1 verification over DB1-DB4", "kind": "verdict"})
        else:
            facts.append({"fact": f"{v['item_code']}: verdict {v['status']} - {v['reason']}", "source": "coordinator",
                          "kind": "verdict"})
    for d, src in result.get("sources", {}).items():
        for sq in src.get("subqueries", []):
            for m in sq.get("matches", []):
                r, t = m["row"], sq["sent"]["target"]
                if t == "ministry_blacklist":
                    facts.append({"fact": f"{r.get('item_ref')} is on the ministry blacklist ({r.get('blacklist_id')}): "
                                          f"{r.get('reason')}", "source": f"{d}.ministry_blacklist", "kind": "blacklist"})
                elif t == "recall_notices":
                    facts.append({"fact": f"{r.get('item_ref')} recalled ({r.get('recall_id')}, class {r.get('recall_class')}): "
                                          f"{r.get('reason')}", "source": f"{d}.recall_notices", "kind": "recall"})
                elif t == "products":
                    facts.append({"fact": f"{r.get('product_uid')} is registered: {r.get('product_name')}, batch "
                                          f"{r.get('batch_number')}, manufacturer {r.get('manufacturer_id')}"
                                          + (f"; RECALLED: {r.get('recall_reason')}" if r.get("is_recalled") else ""),
                                  "source": f"{d}.products", "kind": "registration"})
                elif t == "distribution_batches" and r.get("cold_chain_maintained") == 0:
                    facts.append({"fact": f"shipment {r.get('batch_id')} of {r.get('batch_serial')} did not maintain "
                                          f"the cold chain", "source": f"{d}.distribution_batches", "kind": "cold_chain"})
                elif t == "lab_reports":
                    facts.append({"fact": f"lab report {r.get('lab_report_id')} on {r.get('item_ref')}: {r.get('result')}",
                                  "source": f"{d}.lab_reports", "kind": "lab"})
    seen, out = set(), []
    for f in facts:
        if f["fact"] not in seen:
            seen.add(f["fact"])
            out.append(f)
    return out


def _links(doc: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
    medicines = {m["item_code"]: m for m in result.get("combined", {}).get("medicines", [])}
    links_by = {(l["concept"], l["value"]): l for l in result.get("combined", {}).get("cross_source_links", [])}
    out = []
    for m in doc["matched_entities"]:
        if m["kind"] == "item_code":
            where = medicines.get(m["value"])
            out.append({"entity": f"medicine {m['value']}",
                        "reliability": "reliable (exact code)" if m["match"] == "exact" else "probable (scanner look-alike code)",
                        "structured_records": f"matched in {', '.join(where['matched_in'])}" if where else
                        "no structured record matched this code"})
        elif m["kind"] == "name":
            out.append({"entity": m["value"], "reliability": "weak (name only)", "structured_records": "named in the context"})
        else:
            l = links_by.get((m["kind"], m["value"]))
            out.append({"entity": f"{m['kind'].replace('_', ' ')} {m['value']}", "reliability": "reliable (exact identifier)",
                        "structured_records": f"held by {', '.join(l['databases'])}" if l else "in the query context"})
    return out


ALLEGATION = re.compile(r"\b(fake|counterfeit|spurious|forged|hologram)\b", re.I)


def integrated_response(result: Dict[str, Any]) -> Dict[str, Any]:
    facts = _structured_facts(result)
    blacklisted = {f["fact"].split(" ")[0] for f in facts if f["kind"] == "blacklist"}
    verdict_of = {v["item_code"]: v.get("verdict") for v in result.get("verdicts", [])}
    docs = []
    for d in result.get("document_search", {}).get("documents", []):
        item = {k: d[k] for k in ("doc_id", "title", "type", "date", "owner_database", "file", "source",
                                  "score", "score_parts", "why_retrieved", "matched_terms", "evidence_status")}
        item["provenance"] = {"database": d["owner_database"], "file": d["file"], "source": d["source"],
                              "chunk": f"{d['best_chunk']['n'] + 1} of {d['best_chunk']['of']}"}
        item["matching_context"] = d["best_chunk"]["text"]
        item["linked_structured_entities"] = _links(d, result)
        if "not verified" in d["evidence_status"] and ALLEGATION.search(d["best_chunk"]["text"]):
            codes = [m["value"] for m in d["matched_entities"] if m["kind"] == "item_code"] or d["medicine_ids"][:1]
            notes = []
            for c in codes:
                notes.append(f"{c}: " + ("blacklisted in DB4" if c in blacklisted else "not on the blacklist")
                             + (f"; verdict {verdict_of[c]}" if verdict_of.get(c) else ""))
            item["caution"] = ("An allegation in an unverified report, not proof of counterfeiting. "
                               + ("Structured records: " + "; ".join(notes) if notes else ""))
        docs.append(item)
    local = {}
    for db, src in result.get("sources", {}).items():
        for sq in src.get("subqueries", []):
            sc = sq.get("score_context")
            if sc:
                local.setdefault(db, []).append({
                    "subquery_id": sq["subquery_id"], "explored_tables": sc["explored_tables"],
                    "top_terms": [{"term": t["term"], "where": f"{t['source']['table']}.{t['source']['column']}",
                                   "score": t["score"], "path": " > ".join(t["relationship_path"])}
                                  for t in sc["ranked_context"][:8]]})
    qc = result.get("query_context", {})
    return {
        "A_question": result["question"],
        "B_structured_results": {
            "verified_facts": facts,
            "per_database": {db: {"status": src["status"], "served_by": (src.get("served_by") or {}).get("physical_host"),
                                  "subqueries": [{"id": sq["subquery_id"], "native_query": sq["native_query"],
                                                  "rows": len(sq["matches"])} for sq in src["subqueries"]]}
                             for db, src in result.get("sources", {}).items()},
        },
        "C_local_context": local,
        "D_aggregated_context": {"anchors": qc.get("anchors", []),
                                 "terms": [{"term": t["term"], "score": t["score"], "databases": t["databases"],
                                            "why": t["why_relevant"]} for t in qc.get("terms", [])[:15]]},
        "E_documents": docs,
        "F_G_H": "each document carries its score and score_parts (F), provenance (G) and why_retrieved (H)",
        "policy": ("Verified facts come from the structured databases. Documents report information: an "
                   "official notice or regulatory finding is authoritative text but is not a database record, and a "
                   "consumer or pharmacy report is an unverified allegation. Documents never change the verdict."),
    }
