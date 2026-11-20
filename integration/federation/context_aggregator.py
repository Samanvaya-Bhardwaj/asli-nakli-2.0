"""
context_aggregator.py
---------------------
Combines the local query contexts the databases discovered (each with SCORE, on
its own machine) into ONE overall query context. The coordinator only merges
and ranks here: it never reads a database row itself.

For every term returned by any database:

  local score   s_d = term score / best term score of that subquery's context
                      (so a database with long text columns cannot drown out one
                      with short codes), times the subquery's match quality
                      (1.0 exact, 0.97 formatting, 0.9 scanner look-alike);
                      the best value over that database's subqueries is kept
  corroboration c   = 1 + 0.25 x (number of databases that found it - 1)
  query match   q   = 1.5 if it matches the question's words or intent phrases
  overall       S   = (sum over databases of s_d) x c x q

Terms are deduplicated on a normalised key: an identifier is the same term
whichever database holds it (DIST-001 in DB1's goods receipts, DB2's shipments
and DB3's authorisations), so it is kept once with the provenance of all three.
Every term keeps its full provenance and an explanation of why it is relevant.
"""

from __future__ import annotations
from typing import Any, Dict, List

CORROBORATION = 0.25
QUERY_MATCH = 1.5


def aggregate(per_db: Dict[str, Dict[str, Any]], top_n: int = 25, anchors: List[str] = ()) -> Dict[str, Any]:
    """`anchors`: the question's own identifiers. They are reported apart: the code a user
    asked about is what the context is about, not context about it."""
    anchor_keys = {f"id:{a.strip().upper()}" for a in anchors}
    terms: Dict[str, Dict[str, Any]] = {}
    contributing = {}
    for d, res in per_db.items():
        for sq in res.get("subqueries", []):
            sc = sq.get("score_context")
            if not sc or not sc["ranked_context"]:
                continue
            quality = max((m["score"] for m in sq["matches"]), default=1.0)
            top = max(t["score"] for t in sc["ranked_context"]) or 1.0
            contributing.setdefault(d, []).append(sq["subquery_id"])
            for t in sc["ranked_context"]:
                s = t["score"] / top * quality
                e = terms.setdefault(t["key"], {"key": t["key"], "term": t["term"], "kind": t["kind"],
                                                "by_database": {}, "query_match": False, "provenance": []})
                if s > e["by_database"].get(d, 0.0):
                    e["by_database"][d] = round(s, 4)
                    if s >= max(e["by_database"].values()):
                        e["term"] = t["term"]
                e["query_match"] = e["query_match"] or t["query_match"]
                for o in t["occurrences"]:
                    e["provenance"].append({"subquery_id": sq["subquery_id"], **o})

    ranked = []
    for e in terms.values():
        n = len(e["by_database"])
        score = sum(e["by_database"].values()) * (1 + CORROBORATION * (n - 1)) * (QUERY_MATCH if e["query_match"] else 1.0)
        best = max(e["provenance"], key=lambda o: o["weight"])
        why = []
        steps = sorted({o["augmentation_step"] for o in e["provenance"]})
        if 0 in steps:
            why.append("in the result of the subquery itself")
        if any(s > 0 for s in steps):
            hops = min(s for s in steps if s > 0)
            why.append(f"reached through {hops} FK join(s): {' > '.join(next(o for o in e['provenance'] if o['augmentation_step'] == hops)['relationship_path'])}")
        if n > 1:
            why.append(f"found independently by {n} databases ({', '.join(sorted(e['by_database']))})")
        if e["query_match"]:
            why.append("matches the question's words or intent")
        if best["weight"] >= 0.5 and not e["query_match"]:
            why.append("frequent in the result but rare in its column across the database (high tf x idf)")
        ranked.append({"term": e["term"], "key": e["key"], "kind": e["kind"], "score": round(score, 4),
                       "databases": sorted(e["by_database"]), "local_scores": e["by_database"],
                       "query_match": e["query_match"], "why_relevant": why,
                       "provenance": _dedupe(e["provenance"])[:8]})
    ranked.sort(key=lambda r: (-r["score"], r["key"]))
    anchored = [r for r in ranked if r["key"] in anchor_keys]
    ranked = [r for r in ranked if r["key"] not in anchor_keys]
    return {
        "anchors": [{"term": r["term"], "databases": r["databases"]} for r in anchored],
        "method": "SCORE local contexts, normalised per subquery, deduplicated by term, "
                  "boosted for cross-database corroboration and query match",
        "databases_contributing": {d: ids for d, ids in contributing.items()},
        "distinct_terms": len(ranked),
        "terms": ranked[:top_n],
    }


def _dedupe(prov: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for o in sorted(prov, key=lambda o: -o["weight"]):
        k = (o["database"], o["table"], o["column"], tuple(o["relationship_path"]))
        if k not in seen:
            seen.add(k)
            out.append(o)
    return out
