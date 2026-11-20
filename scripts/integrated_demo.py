#!/usr/bin/env python3
"""
integrated_demo.py
------------------
Context-aware document retrieval and the integrated answer, through the
coordinator's HTTP API:

  1. the question
  2. the aggregated query context (SCORE, from the four databases)
  3. the document search query built from that context
  4. the documents retrieved (each source searched its own collection)
  5. the relevance ranking, with every score's parts
  6. the integrated response: verified structured facts, then what documents report

    python scripts/integrated_demo.py "Find information about batch BATCH-A009 manufactured by Biocon and identify any quality or safety concerns"
    python scripts/integrated_demo.py --no-context "..."    # the same search WITHOUT the context, for comparison
"""

from __future__ import annotations
import argparse
import json
import os
import urllib.request

LINE = "=" * 104


def post(base, path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def cut(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 3] + "..."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--coordinator", default=os.environ.get("ASALI_COORDINATOR_URL", "http://127.0.0.1:8030"))
    ap.add_argument("--token", default=os.environ.get("ASALI_COORDINATOR_TOKEN"))
    ap.add_argument("--save")
    a = ap.parse_args()
    res = post(a.coordinator, "/api/v3/federated/query", {"query": a.question, "verify": True}, a.token)
    integ, ds = res["integrated"], res["document_search"]

    print(LINE)
    print(f"1. QUESTION: {integ['A_question']}")
    u = res["understanding"]
    print(f"   intents {u['intents']}; identifiers {u['item_codes'] + u['batch_numbers'] + u['vendor_ids'] + u['distributor_ids'] + u['manufacturer_ids']}; "
          f"terms {u['terms']}; databases queried {res['routing']['databases']}")
    print(LINE)
    qc = integ["D_aggregated_context"]
    print(f"2. AGGREGATED CONTEXT  (anchors: {', '.join(x['term'] for x in qc['anchors']) or '-'})")
    for t in qc["terms"][:12]:
        print(f"   {t['score']:<7} {cut(t['term'], 50):<50} {'/'.join(t['databases']):<10} {cut('; '.join(t['why']), 80)}")
    print(LINE)
    print("3. DOCUMENT SEARCH QUERY BUILT FROM THE CONTEXT")
    print("   " + ds["request"]["display"].replace("\n", "\n   "))
    print(LINE)
    print("4. DOCUMENT STORES SEARCHED (each by its own source)")
    for d, p in ds["per_database"].items():
        print(f"   {d}: {p['status']}, {p.get('documents_searched', 0)} documents / {p.get('chunks_searched', 0)} chunks, "
              f"{p.get('passed_relevance_gate', 0)} passed the relevance gate, {p['returned']} returned")
    print(LINE)
    print("5. RANKING")
    for i, d in enumerate(integ["E_documents"], 1):
        sp = d["score_parts"]
        print(f"   #{i} {d['score']:<7} {d['doc_id']:<16} {cut(d['title'], 52):<52} [{d['type']}] {d['date']}")
        print(f"        parts: lexical {sp['lexical']}  entity {sp['entity']}  type x{sp['type']}  recency x{sp['recency']}"
              f"  conflict x{sp['conflict']}   | owner {d['provenance']['database']} / {d['provenance']['file']} "
              f"(chunk {d['provenance']['chunk']}); {d['source']}")
        print(f"        why: {cut('; '.join(d['why_retrieved']), 150)}")
        print(f"        evidence: {d['evidence_status']}")
        print(f"        matching context: \"{cut(d['matching_context'], 210)}\"")
        for l in d["linked_structured_entities"][:3]:
            print(f"        link: {l['entity']} - {l['reliability']}; {l['structured_records']}")
        if d.get("caution"):
            print(f"        CAUTION: {d['caution']}")
    print(LINE)
    print("6. INTEGRATED RESPONSE")
    print("   VERIFIED (structured records):")
    for f in integ["B_structured_results"]["verified_facts"][:10]:
        print(f"     - {cut(f['fact'], 140)}   [{f['source']}]")
    print("   REPORTED IN DOCUMENTS:")
    for d in integ["E_documents"][:6]:
        print(f"     - {d['title']} ({d['evidence_status']}, {d['provenance']['database']}): \"{cut(d['matching_context'], 110)}\"")
    print(f"   POLICY: {integ['policy']}")
    print(LINE)
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, default=str)


if __name__ == "__main__":
    main()
