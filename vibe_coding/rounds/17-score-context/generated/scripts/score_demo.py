#!/usr/bin/env python3
"""
score_demo.py
-------------
Shows SCORE-inspired query context discovery for one question, through the
coordinator's HTTP API (the discovery itself runs inside each database service):

  1. the initial SQL (or document) result of each subquery
  2. the neighbouring tables each database explored, and the ones it did not
  3. the FK-PK joins it performed, with their relevance
  4. the context terms extracted (tf x idf weights)
  5. the local context each database returned
  6. the final aggregated context
  7. why each aggregated term is relevant to the question

    python scripts/score_demo.py "Was the cold chain of MED-ASALI-009 maintained?"
    python scripts/score_demo.py --max-augmentation 2 --top-n 10 "..."
"""

from __future__ import annotations
import argparse
import json
import os
import urllib.request

LINE = "=" * 100


def post(base, path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def cut(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n - 3] + "..."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--coordinator", default=os.environ.get("ASALI_COORDINATOR_URL", "http://127.0.0.1:8030"))
    ap.add_argument("--token", default=os.environ.get("ASALI_COORDINATOR_TOKEN"))
    ap.add_argument("--max-augmentation", type=int)
    ap.add_argument("--top-n", type=int)
    ap.add_argument("--save")
    a = ap.parse_args()
    res = post(a.coordinator, "/api/v3/federated/query",
               {"query": a.question, "verify": False, "max_augmentation": a.max_augmentation, "top_n": a.top_n}, a.token)

    u = res["understanding"]
    print(LINE)
    print(f"QUESTION: {res['question']}")
    print(f"  intents {u['intents']}  identifiers {u['item_codes'] + u['vendor_ids'] + u['distributor_ids'] + u['manufacturer_ids']}"
          f"  terms {u['terms']}")
    print(f"  context keywords sent to every database: {u['context_keywords']}")
    print(f"  databases: {', '.join(res['routing']['databases'])}"
          + (f"   (not queried: {', '.join(res['routing']['not_queried'])})" if res["routing"]["not_queried"] else ""))
    for d, src in res["sources"].items():
        sb = src.get("served_by") or {}
        for sq in src["subqueries"]:
            sc = sq.get("score_context")
            print(LINE)
            print(f"[{d}] {sq['subquery_id']}  executed by pid {sb.get('pid')} on {sb.get('physical_host')} ({sb.get('listening_on')})")
            print(f"  1. INITIAL RESULT: {cut(sq['native_query'], 160)}   params {sq['params']}")
            print(f"     -> {len(sq['matches'])} row(s) of {sq['sent']['target']}"
                  + (f" [{', '.join(sorted({m['match'] for m in sq['matches']}))}]" if sq["matches"] else ""))
            if not sc:
                print("     (no rows, so no context to discover)")
                continue
            kinds = sc["query_result"]["column_kinds"]
            print(f"     all {len(kinds)} columns kept: " + ", ".join(f"{c}:{k}" for c, k in kinds.items() if k != "skip")[:220])
            print(f"  2. SCHEMA GRAPH: {len(sc['schema_graph']['nodes'])} tables, {len(sc['schema_graph']['edges'])} FK edges "
                  f"(read from the database). Parameters {sc['parameters']}")
            print(f"  3. AUGMENTATION (greedy: join the most relevant FK, then re-evaluate)")
            for st in sc["augmentation"]:
                for c in st["candidates"]:
                    mark = "JOIN " if c.get("chosen") else "     "
                    print(f"     step {st['step']} {mark}{c['fk_relevance']:<8} {c['from']} -> {c['to']:<26} "
                          f"{c['direction']:<26} rows {c['joined_rows']:<3} new terms {c['new_terms']:<3} affinity {c['schema_affinity']}")
            print(f"     stop: {sc['stop_reason']}")
            for j in sc["joins_performed"]:
                print(f"     join {j['step']}: {cut(j['join'], 170)}  -> {j['joined_rows']} row(s)")
            not_explored = sorted(set(sc["schema_graph"]["nodes"]) - set(sc["explored_tables"]))
            print(f"     explored {sc['explored_tables']}; not explored {not_explored}")
            print(f"  4. TERMS FROM THE RESULT (tf x idf): " + "; ".join(f"{t['term']} {t['weight']}" for t in sc["result_terms"][:8]))
            print(f"  5. LOCAL CONTEXT returned by {d} (top {len(sc['ranked_context'])}):")
            for t in sc["ranked_context"][:10]:
                print(f"     {t['score']:<8} {cut(t['term'], 58):<58} {t['source']['table']}.{t['source']['column']:<24} "
                      f"via {cut(' > '.join(t['relationship_path']), 60)}{'  [query]' if t['query_match'] else ''}")
    qc = res["query_context"]
    print(LINE)
    print(f"6. AGGREGATED QUERY CONTEXT: {qc['distinct_terms']} distinct terms from {', '.join(qc['databases_contributing'])}; top {len(qc['terms'])}")
    for t in qc["terms"][:20]:
        print(f"   {t['score']:<7} {cut(t['term'], 52):<52} {'/'.join(t['databases']):<12} {t['kind']}")
        print(f"           7. why: {'; '.join(t['why_relevant'])}")
    print(LINE)
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, default=str)


if __name__ == "__main__":
    main()
