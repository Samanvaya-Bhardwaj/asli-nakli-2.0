"""The asking node merges the contexts the organisations found into one context for the question.

Carried over from `integration/federation/context_aggregator.py`. The mediator only merges and ranks: it never
reads another organisation's rows, only the terms each organisation chose to return.

For every term returned by any organisation:
  local score    s_o = its score / the best score of that organisation's context, so an organisation with long
                 text columns cannot drown out one with short codes
  corroboration  c   = 1 + 0.25 x (organisations that found it - 1)
  question match q   = 1.5 when it matches the question's words
  overall        S   = (sum of s_o) x c x q
Terms are merged on their normalised key, so the same lot number found in three organisations is one term
with three provenances.
"""

from typing import Any

CORROBORATION = 0.25
QUERY_MATCH = 1.5


def aggregate(
    per_org: dict[str, dict[str, Any]], top_n: int = 25, anchors: list[str] | None = None
) -> dict[str, Any]:
    """`anchors` are the identifiers the question named. They are what the context is about, not context about it."""
    anchor_values = {a.strip().upper() for a in anchors or []}
    anchor_keys = {f"id:{a}" for a in anchor_values}
    terms: dict[str, dict[str, Any]] = {}
    contributing: list[str] = []
    for org, res in per_org.items():
        ranked = res.get("ranked_context") or []
        if not ranked:
            continue
        contributing.append(org)
        top = max(t["score"] for t in ranked) or 1.0
        for t in ranked:
            s = t["score"] / top
            e = terms.setdefault(t["key"], {"key": t["key"], "term": t["term"], "kind": t["kind"], "by_org": {},
                                            "query_match": False, "provenance": []})  # fmt: skip
            if s > e["by_org"].get(org, 0.0):
                e["by_org"][org] = round(s, 4)
                if s >= max(e["by_org"].values()):
                    e["term"] = t["term"]
            e["query_match"] = e["query_match"] or t["query_match"]
            e["provenance"].append({"organisation": org, **t["source"], "step": t["step"],
                                    "relationship_path": t["relationship_path"], "weight": t["score"]})  # fmt: skip
    ranked_terms = []
    for e in terms.values():
        n = len(e["by_org"])
        score = (
            sum(e["by_org"].values())
            * (1 + CORROBORATION * (n - 1))
            * (QUERY_MATCH if e["query_match"] else 1.0)
        )
        why = []
        steps = sorted({o["step"] for o in e["provenance"]})
        if 0 in steps:
            why.append("in the rows that mention the pack")
        deeper = [s for s in steps if s > 0]
        if deeper:
            hops = min(deeper)
            first = next(o for o in e["provenance"] if o["step"] == hops)
            why.append(
                f"reached through {hops} foreign key join(s): {' > '.join(first['relationship_path'])}"
            )
        if n > 1:
            why.append(f"found independently by {n} organisations ({', '.join(sorted(e['by_org']))})")
        if e["query_match"]:
            why.append("matches the question's words")
        ranked_terms.append({"term": e["term"], "key": e["key"], "kind": e["kind"], "score": round(score, 4),
                             "organisations": sorted(e["by_org"]), "local_scores": e["by_org"],
                             "query_match": e["query_match"], "why_relevant": why,
                             "provenance": _dedupe(e["provenance"])[:6]})  # fmt: skip
    ranked_terms.sort(key=lambda r: (-r["score"], r["key"]))

    def is_anchor(r: dict[str, Any]) -> bool:
        return r["key"] in anchor_keys or str(r["term"]).rsplit("=", 1)[-1].strip().upper() in anchor_values

    anchored = [r for r in ranked_terms if is_anchor(r)]
    return {
        "method": "SCORE contexts from each organisation, normalised per organisation, merged by term, "
        "boosted for corroboration and for matching the question",
        "anchors": [{"term": r["term"], "organisations": r["organisations"]} for r in anchored],
        "organisations_asked": sorted(per_org),
        "organisations_contributing": sorted(contributing),
        "distinct_terms": len(ranked_terms) - len(anchored),
        "terms": [r for r in ranked_terms if not is_anchor(r)][:top_n],
    }


def _dedupe(prov: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out = []
    for o in sorted(prov, key=lambda o: -o["weight"]):
        k = (o["organisation"], o["table"], o["column"], tuple(o["relationship_path"]))
        if k not in seen:
            seen.add(k)
            out.append(o)
    return out
