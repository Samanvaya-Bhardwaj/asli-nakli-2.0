#!/usr/bin/env python3
"""
phase3_scenarios.py
-------------------
Runs the three Phase 3 demonstration scenarios against a running coordinator and
writes, from the real responses only:

  phase3/documentation/evidence/scenario_N.json   the complete response
  phase3/documentation/evidence/nodes.json        the deployment as the coordinator saw it
  phase3/documentation/PHASE3_DEMONSTRATION.md    the walkthrough generated from those responses

Nothing in the generated document is written by hand: rerun this to refresh it.

    python scripts/run_federation.py --env-file deploy/local.env       # in another terminal
    python scripts/phase3_scenarios.py [--coordinator http://<machine1>:8030]
"""

from __future__ import annotations
import argparse
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(BASE, "phase3", "documentation")
EVIDENCE = os.path.join(DOC_DIR, "evidence")
SCENARIOS = [
    ("Scenario 1 - medicine and batch verification", "Is MED-ASALI-009 from batch BATCH-A009 genuine?"),
    ("Scenario 2 - manufacturer and quality",
     "Any quality or safety concerns about products manufactured by MFG-002 (Sun Pharmaceutical)?"),
    ("Scenario 3 - regulatory action and consumer complaints",
     "Are there consumer complaints or regulatory action against MED-NAKALI-001?"),
]


def call(base, path, body=None):
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def md_cell(s, n=None):
    s = " ".join(str(s).split()).replace("|", "\\|")
    return s if n is None or len(s) <= n else s[:n - 3] + "..."


def scenario_md(title, res, n):
    u, I, ds = res["understanding"], res["integrated"], res["document_search"]
    L = [f"## {title}", "", f"Evidence: `evidence/scenario_{n}.json` (query `{res['query_id']}`, {res['timing_ms']['total']} ms).", "",
         "### 1. The user's question", "", f"> {res['question']}", "",
         "How it was read: " + "; ".join(u["explanation"]) + ".", "",
         "Databases asked: " + "; ".join(f"**{d}** ({', '.join(w)})" for d, w in res["routing"]["reasons"].items()) + "."]
    if res["routing"]["not_queried"]:
        L.append("Not asked: " + "; ".join(f"{d} ({w})" for d, w in res["routing"]["not_queried"].items()) + ".")
    L += ["", "### 2. Generated database-specific subqueries (GAV unfolding)", "",
          "| Subquery | Database | Target (its own table) | Condition | Native query it ran |", "|---|---|---|---|---|"]
    for d, src in res["sources"].items():
        for sq in src["subqueries"]:
            cond = " AND ".join(f"{w['field']} {w['op']} {w['value']}" for w in sq["sent"]["where"])
            L.append(f"| {sq['subquery_id']} | {d} | {sq['sent']['target']} | `{md_cell(cond, 80)}` | `{md_cell(sq['native_query'], 110)}` |")
    L += ["", "### 3. Structured results from each database", "",
          "| Database | Status | Served by (pid @ host) | Rows matched |", "|---|---|---|---|"]
    for d, src in res["sources"].items():
        sb = src.get("served_by") or {}
        L.append(f"| {d} | {src['status']} | {sb.get('pid')} @ {sb.get('physical_host')} ({sb.get('listening_on')}) | "
                 + ", ".join(f"{sq['sent']['target']}: {len(sq['matches'])}" for sq in src["subqueries"]) + " |")
    L += ["", "Verified facts (structured records):", ""]
    L += [f"- {f['fact']} — *{f['source']}*" for f in I["B_structured_results"]["verified_facts"]] or ["- none"]
    L += ["", "### 4. FK-PK relationships explored (SCORE augmentation, inside each database)", ""]
    for d, src in res["sources"].items():
        for sq in src["subqueries"]:
            sc = sq.get("score_context")
            if not sc:
                continue
            L.append(f"**{d} / {sq['subquery_id']}** — result relation: {sc['query_result']['rows']} row(s) of "
                     f"`{sc['query_result']['table']}`; explored {' → '.join(sc['explored_tables'])}; stop: {sc['stop_reason']}.")
            L.append("")
            L.append("| Step | FK join chosen | Relevance | Other candidates (relevance) |")
            L.append("|---|---|---|---|")
            for st in sc["augmentation"]:
                chosen = next((c for c in st["candidates"] if c.get("chosen")), None)
                others = ", ".join(f"{c['to']} ({c['fk_relevance']})" for c in st["candidates"] if not c.get("chosen"))
                L.append(f"| {st['step']} | `{chosen['fk'] if chosen else '- (none above threshold)'}` | "
                         f"{chosen['fk_relevance'] if chosen else '-'} | {md_cell(others, 120) or '-'} |")
            L.append("")
    L += ["### 5. Context discovered by each database", ""]
    for d, items in I["C_local_context"].items():
        for item in items:
            L.append(f"**{d} / {item['subquery_id']}**: " + "; ".join(
                f"{md_cell(t['term'], 40)} ({t['score']}, {t['where']}{'' if t['path'] == '(query result)' else ' via ' + t['path']})"
                for t in item["top_terms"][:6]))
            L.append("")
    L += ["### 6. Aggregated overall context", "", "Anchors (what the question is about): "
          + (", ".join(a["term"] for a in I["D_aggregated_context"]["anchors"]) or "-"), "",
          "| Term | Score | Found by | Why relevant |", "|---|---|---|---|"]
    for t in I["D_aggregated_context"]["terms"][:12]:
        L.append(f"| {md_cell(t['term'], 50)} | {t['score']} | {', '.join(t['databases'])} | {md_cell('; '.join(t['why']), 140)} |")
    L += ["", "### 7. Generated unstructured search query", "", "```", ds["request"]["display"], "```", "",
          "Document stores searched: " + "; ".join(
              f"{d}: {p['status']}, {p.get('documents_searched', 0)} documents, {p['returned']} returned"
              for d, p in ds["per_database"].items()) + ".", "",
          "### 8. Retrieved documents and relevance scores", "",
          "| # | Score | Document | Type | Owner / file | Why retrieved |", "|---|---|---|---|---|---|"]
    for i, d in enumerate(I["E_documents"], 1):
        L.append(f"| {i} | {d['score']} | {md_cell(d['title'], 60)} | {d['type']} | {d['provenance']['database']} / "
                 f"`{d['provenance']['file']}` | {md_cell('; '.join(d['why_retrieved']), 150)} |")
    L += ["", "### 9. Final integrated response", ""]
    v = res["verdicts"][0] if res["verdicts"] else None
    if v:
        L.append(f"**Verdict (Phase 1 engine, unchanged):** {v['item_code']}: " +
                 (f"{v['verdict']}, trust {v['trust_score']}, vetoes {v['veto_codes'] or 'none'}" if v["status"] == "COMPUTED"
                  else f"{v['status']} — {v['reason']}"))
        L.append("")
    L.append("**Reported in documents** (evidence status; never changes the verdict):")
    L.append("")
    for d in I["E_documents"][:6]:
        L.append(f"- *{d['title']}* — {d['evidence_status']}; {d['provenance']['database']}/{d['provenance']['file']}, "
                 f"chunk {d['provenance']['chunk']}: \"{md_cell(d['matching_context'].replace('**', ''), 200)}\"")
        if d.get("caution"):
            L.append(f"  - **Caution:** {d['caution']}")
    L += ["", f"Policy: {I['policy']}", ""]
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coordinator", default=os.environ.get("ASALI_COORDINATOR_URL", "http://127.0.0.1:8030"))
    a = ap.parse_args()
    os.makedirs(EVIDENCE, exist_ok=True)
    nodes = call(a.coordinator, "/api/v3/federation/nodes")
    json.dump(nodes, open(os.path.join(EVIDENCE, "nodes.json"), "w", encoding="utf-8"), indent=1, default=str)
    L = ["# Phase 3 demonstration", "",
         "*Generated by `scripts/phase3_scenarios.py` from real responses of the running system on "
         f"{time.strftime('%Y-%m-%d %H:%M')}; the full responses are in `evidence/`. Nothing below is written by hand.*", "",
         f"**Deployment observed:** `{nodes['deployment']['mode']}` — {nodes['deployment']['meaning']}", "",
         "| Database | Address | Resolved IP | Host (label, pid) |", "|---|---|---|---|"]
    for d, n in nodes["nodes"].items():
        r = n.get("reported", {})
        L.append(f"| {d} {n.get('name', '')} | {n.get('configured_url')} | {n.get('resolved_ip')} | "
                 f"{r.get('physical_host')} ({r.get('machine_label')}, {r.get('pid')}) |")
    L += ["", "The same three questions are offered as buttons on the coordinator's page (`http://<coordinator>:8030/`), "
          "which shows each stage below for any question.", ""]
    for n, (title, q) in enumerate(SCENARIOS, 1):
        res = call(a.coordinator, "/api/v3/federated/query", {"query": q})
        json.dump(res, open(os.path.join(EVIDENCE, f"scenario_{n}.json"), "w", encoding="utf-8"), indent=1, default=str)
        L += scenario_md(title, res, n)
        print(f"  {title}: {len(res['integrated']['E_documents'])} documents, verdict "
              f"{(res['verdicts'][0].get('verdict') or res['verdicts'][0]['status']) if res['verdicts'] else '-'}")
    with open(os.path.join(DOC_DIR, "PHASE3_DEMONSTRATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"  -> {os.path.join(DOC_DIR, 'PHASE3_DEMONSTRATION.md')}")


if __name__ == "__main__":
    main()
