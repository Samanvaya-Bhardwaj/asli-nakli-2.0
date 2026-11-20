#!/usr/bin/env python3
"""
eval_retrieval.py
-----------------
Does the discovered context improve document retrieval? For a set of questions,
runs the Phase 3 pipeline in-process (the same code each database service runs:
subqueries, SCORE context, aggregation, per-source document search; read-only,
no HTTP) twice:

  with context     the search request built from the aggregated SCORE context
  question only    the same search, given only the question's text and its own identifiers

and scores both against data/documents/ground_truth.json (a document is relevant
when it is truly about one of the medicines the question is about).

    python scripts/eval_retrieval.py
"""

from __future__ import annotations
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from integration.federation import coordinator, runtime                     # noqa: E402
from integration.federation.context_aggregator import aggregate            # noqa: E402
from integration.federation.doc_store import store                         # noqa: E402
from integration.federation.local_engine import NodeEngine                 # noqa: E402
from integration.federation.query_parser import parse                      # noqa: E402
from integration.federation.retrieval import build_search_request          # noqa: E402

# question -> the medicines it is about (the judgement the ground truth is checked against)
QUESTIONS = {
    "Was the cold chain of MED-ASALI-009 maintained?": ["MED-ASALI-009"],
    "Find information about batch BATCH-A009 manufactured by Biocon and identify any quality or safety concerns": ["MED-ASALI-009"],
    "Has MED-RECALL-001 been recalled, and why?": ["MED-RECALL-001"],
    "Is MED-NAKALI-001 counterfeit?": ["MED-NAKALI-001"],
    "Any quality concerns about batch BATCH-R002?": ["MED-RECALL-002"],
    "Is MED-ASALI-005 genuine?": ["MED-ASALI-005"],
    "Was MED-UNAUTH-001 shipped through an authorised distributor?": ["MED-UNAUTH-001"],
    "verify med asal1 oo1": ["MED-ASALI-001"],
    "Safety concerns about MED-RECALL-003": ["MED-RECALL-003"],
    "Was the cold chain of MED-UNAUTH-002 maintained?": ["MED-UNAUTH-002"],
}
K = 5


def run_inprocess(question: str, use_context: bool = True):
    pq = parse(question)
    routing = coordinator.route(pq)
    plan = coordinator.unfold(pq, routing["databases"], "EVAL")
    per_db = {}
    for d, subs in plan.items():
        eng = NodeEngine(d)
        out = []
        for sq in subs:
            r = eng.run(sq)
            r["sent"], r["concept"] = sq, sq.get("concept")
            out.append(r)
        per_db[d] = {"subqueries": out, "status": "ok"}
    combined = coordinator._combine(per_db)
    anchors = pq.item_codes + coordinator._seed_codes(per_db, pq) + pq.batch_numbers
    qc = aggregate(per_db, top_n=25, anchors=anchors)
    if use_context:
        req = build_search_request(pq, qc, combined, anchors)
    else:      # the question alone: its text and its own identifiers, nothing the databases found
        req = build_search_request(pq, {"terms": []}, {"cross_source_links": []}, pq.item_codes + pq.batch_numbers)
    results = []
    for d in runtime.DB_IDS:
        results.extend(store(d).search({k: v for k, v in req.items() if k != "display"})["results"])
    results.sort(key=lambda r: (-r["score"], r["doc_id"]))
    return req, results[:10], qc


def relevant_docs(truth_codes):
    gt = json.load(open(os.path.join(BASE, "data", "documents", "ground_truth.json"), encoding="utf-8"))["documents"]
    return {doc for doc, g in gt.items() if set(g["item_codes"]) & set(truth_codes)}


def metrics(results, rel):
    ids = [r["doc_id"] for r in results]
    p = sum(1 for d in ids[:K] if d in rel) / K
    r = sum(1 for d in ids if d in rel) / max(1, len(rel))
    dcg = sum(1 / math.log2(i + 2) for i, d in enumerate(ids[:10]) if d in rel)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(10, len(rel))))
    return p, r, (dcg / idcg if idcg else 0.0)


def main():
    rows = []
    for q, truth in QUESTIONS.items():
        rel = relevant_docs(truth)
        _r1, with_ctx, _qc = run_inprocess(q, True)
        _r2, plain, _ = run_inprocess(q, False)
        rows.append((q, len(rel), metrics(with_ctx, rel), metrics(plain, rel)))
    print(f"{'question':<62} rel  | with context P@{K}  R@10  nDCG | question only P@{K}  R@10  nDCG")
    for q, n, a, b in rows:
        print(f"{q[:62]:<62} {n:<4} |       {a[0]:.2f}  {a[1]:.2f}  {a[2]:.2f} |        {b[0]:.2f}  {b[1]:.2f}  {b[2]:.2f}")
    avg = lambda i, j: sum(r[i][j] for r in rows) / len(rows)
    print(f"{'MEAN':<62}      |       {avg(2, 0):.2f}  {avg(2, 1):.2f}  {avg(2, 2):.2f} |        "
          f"{avg(3, 0):.2f}  {avg(3, 1):.2f}  {avg(3, 2):.2f}")
    return rows


if __name__ == "__main__":
    main()
