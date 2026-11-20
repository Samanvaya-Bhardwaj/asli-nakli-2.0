#!/usr/bin/env python3
"""
federated_demo.py
-----------------
Phase 3 Requirement 2 demonstration, through the coordinator's HTTP API:

  1. the four independent database services
  2. their machine addresses (and whether this is a simulation or multi-machine)
  3. one user question
  4. the subquery generated for each database, in its own vocabulary
  5. independent execution on each database (native query, local context, FK paths)
  6. what each database returned
  7. the combined federated result (+ the Phase 1 verdict)

    python scripts/federated_demo.py "Is MED-ASALI-009 genuine and was its cold chain maintained?"
    python scripts/federated_demo.py --coordinator http://192.168.1.10:8030 "complaints about Novamox"
    python scripts/federated_demo.py --save demo.json "..."      # full JSON transcript
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request

LINE = "-" * 96


def call(base, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def short(v, n=110):
    s = json.dumps(v, default=str) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n - 3] + "..."


def main():
    ap = argparse.ArgumentParser(description="Phase 3 federated query demonstration")
    ap.add_argument("question")
    ap.add_argument("--coordinator", default=os.environ.get("ASALI_COORDINATOR_URL", "http://127.0.0.1:8030"))
    ap.add_argument("--token", default=os.environ.get("ASALI_COORDINATOR_TOKEN"))
    ap.add_argument("--max-hops", type=int, default=2)
    ap.add_argument("--save", help="write the full JSON transcript here")
    args = ap.parse_args()

    nodes = call(args.coordinator, "/api/v3/federation/nodes", token=args.token)
    res = call(args.coordinator, "/api/v3/federated/query",
               {"query": args.question, "max_hops": args.max_hops, "verify": True}, token=args.token)

    dep = nodes["deployment"]
    print(LINE)
    print(f"DEPLOYMENT: {dep['mode']}")
    print(f"  {dep['meaning']}")
    c = nodes["coordinator"]
    print(f"  coordinator: host {c['hostname']} (machine '{c['machine_label']}'), {args.coordinator}")
    print(LINE)
    print("1-2. DATABASE SERVICES AND THEIR ADDRESSES")
    for d, n in nodes["nodes"].items():
        r = n.get("reported", {})
        print(f"  {d}  {n.get('name', ''):<22} {n.get('status', ''):<12} {n.get('configured_url', ''):<26} "
              f"ip {n.get('resolved_ip', '-'):<15} host {r.get('physical_host', '-')} "
              f"(label {r.get('machine_label', '-')}, pid {r.get('pid', '-')}, "
              f"{'container' if r.get('in_container') else 'process'}), sees coordinator as {r.get('seen_client', '-')}")
    print(LINE)
    print(f"3. QUESTION: {res['question']}")
    for e in res["understanding"]["explanation"]:
        print(f"     - {e}")
    print("   ROUTING:")
    for d, why in res["routing"]["reasons"].items():
        print(f"     {d}: {'; '.join(why)}")
    for d, why in res["routing"]["not_queried"].items():
        print(f"     {d}: not queried ({why})")
    print(LINE)
    print("4. SUBQUERIES (GAV unfolding into each database's own tables and fields)")
    for d, subs in res["subqueries"].items():
        for s in subs:
            w = s["where"][0]
            print(f"  {s['id']:<14} -> {d}.{s['target']}  WHERE {w['field']} {w['op']} {short(w['value'], 40)}  "
                  f"(+ local context, {s['expand']['max_hops']} FK hops)")
    print(LINE)
    print("5-6. EXECUTION ON EACH DATABASE, AND WHAT IT RETURNED")
    for d, src in res["sources"].items():
        sb = src.get("served_by") or {}
        print(f"  [{d}] status {src['status']}, {src['elapsed_ms']} ms, executed by pid {sb.get('pid', '-')} on "
              f"{sb.get('physical_host', '-')} ({sb.get('listening_on', src['url'])})")
        for e in src["errors"]:
            print(f"      ! {e['subquery_id']}: {e['status']} - {e['message']}")
        for sq in src["subqueries"]:
            print(f"      {sq['subquery_id']}: native query: {short(sq['native_query'], 150)}")
            print(f"        matched {len(sq['matches'])} row(s)"
                  + (f" [{', '.join(sorted({m['match'] for m in sq['matches']}))}]" if sq["matches"] else "")
                  + f"; local context {len(sq['context'])} row(s) {sq['context_summary']}; "
                    f"{sq['local_queries_executed']} local queries; {sq['timing_ms']}")
            for ctx in sq["context"][:3]:
                print(f"          hop {ctx['hop']} score {ctx['score']:<6} {ctx['table']} {short(ctx['pk'], 40)} "
                      f"via {' > '.join(ctx['path'])}")
    print(LINE)
    print("7. COMBINED FEDERATED RESULT")
    for m in res["combined"]["medicines"][:8]:
        print(f"  medicine {m['item_code']:<16} found in {', '.join(m['found_in'])}")
    for link in res["combined"]["cross_source_links"][:8]:
        print(f"  link {link['concept']}={link['value']} shared by {', '.join(link['databases'])}")
    for v in res["verdicts"]:
        if v["status"] == "COMPUTED":
            print(f"  VERDICT {v['item_code']}: {v['verdict']} (trust {v['trust_score']}, vetoes {v['veto_codes'] or 'none'}, "
                  f"lifecycle {v['lifecycle_state']}) - {v['computed_by']}")
        else:
            print(f"  VERDICT {v['item_code']}: {v['status']} - {v['reason']} {v.get('unavailable', '')}")
    print(f"  partial result: {res['partial']}   source status: {res['source_status']}   "
          f"time: {res['timing_ms']}")
    print(LINE)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "result": res}, f, indent=2, default=str)
        print(f"full transcript -> {args.save}")


if __name__ == "__main__":
    main()
