"""SCORE-inspired query context, discovered by one node inside its own database.

Carried over from the Phase 3 code (`integration/federation/score_context.py`), rewritten to run on the
node's own PostgreSQL, SQLite or MongoDB through `graph.py`, and to leave out anything that could name a person
or another pack. The idea, as in SCORE: the rows that answer the query say what it is about; the tables next
to them, reached through foreign keys, say more.

  1. The result relation R0 is the set of rows that mention the pack (found by the store).
  2. Terms are taken from R0 per column kind (words, categories, identifiers, dates, one summary per numeric
     column) and weighted  w = tf x idf x kind weight x decay x query boost.
     tf is the share of R0 rows holding the term; idf is how rare it is in that column across the table, so a
     value common in R0 but rare in the table outranks one every row has.
  3. Augmentation, greedy: for every foreign key from an explored table to an unexplored one, join from the
     current relation, take the joined rows' terms, and score the key
         relevance = (sum of the 5 best NEW term weights) x (1 + affinity) x fan-out penalty
     Join the best key, repeat until MAX_AUGMENTATION joins or no key reaches MIN_FK_RELEVANCE. A key whose join
     gives no rows scores 0 and is never followed.
  4. Terms are merged by key and the TOP_N returned, each with its table, column and the path of joins.

The tf x idf, top-5 gain, affinity and fan-out formulas are this project's reading of the lecture; every number
is a parameter in DEFAULTS.
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from asali_node.context.graph import Edge, Graph

DEFAULTS: dict[str, Any] = {
    "max_augmentation": 4,
    "top_n": 20,
    "decay": 0.7,
    "min_fk_relevance": 0.05,
    "join_cap": 200,
    "query_boost": 1.0,
    "affinity_boost": 1.0,
    "gain_top_k": 5,
}
KIND_WEIGHT = {"text": 1.0, "identifier": 0.9, "categorical": 0.8, "numeric": 0.6, "date": 0.5}
# Never a term: secrets, anything that could identify a person or a device, and the codes of other packs.
SKIP_NAME = re.compile(
    r"(hash|password|token|phone|email|contact|device|barcode|raw|reasons_json|(^|[_.])(sn|serial|srl|srl_no|s)($|[_.]))",
    re.I,
)
ID_NAME = re.compile(r"(_id|_ref|_uid|_no|^_id$|licen[cs]e|code|number)$", re.I)
DATE_NAME = re.compile(
    r"(date|_on$|_at$|timestamp|expiry|expires|since|until|time|_dt$|_ts$|^at$|^when$)", re.I
)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
WORD = re.compile(r"[a-z][a-z0-9+\-]{2,}")
STOPWORDS = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "not",
        "but",
        "all",
        "can",
        "will",
        "would",
        "could",
        "their",
        "there",
        "been",
        "into",
        "than",
        "then",
        "them",
        "they",
        "its",
        "our",
        "out",
        "per",
        "any",
        "may",
        "who",
        "which",
        "when",
        "what",
    ]
)


@dataclass
class Profile:
    column: str
    kind: str
    n_rows: int
    value_df: Counter[str] = field(default_factory=Counter)
    token_df: Counter[str] = field(default_factory=Counter)
    mean: float = 0.0
    std: float = 0.0


def _num(v: Any) -> float | None:
    return None if isinstance(v, bool) or not isinstance(v, int | float) else float(v)


def _tokens(v: Any) -> list[str]:
    return [t for t in WORD.findall(str(v).lower()) if t not in STOPWORDS]


def classify(column: str, values: list[Any], is_key: bool) -> str:
    vals = [v for v in values if v not in (None, "")]
    if not vals or SKIP_NAME.search(column):
        return "skip"
    if is_key:
        return "identifier"
    nums = [_num(v) for v in vals]
    distinct = len({str(v) for v in vals})
    if all(n is not None for n in nums):
        if ID_NAME.search(column):
            return "identifier"
        return (
            "categorical"
            if distinct <= 5 and all(float(n).is_integer() for n in nums if n is not None)
            else "numeric"
        )
    strs = [str(v) for v in vals]
    if DATE_NAME.search(column) or sum(1 for s in strs if ISO.match(s)) > 0.8 * len(strs):
        return "date"
    if ID_NAME.search(column):
        return "identifier"
    avg_words = sum(len(s.split()) for s in strs) / len(strs)
    if avg_words >= 4:
        return "text"
    if distinct <= max(12, 0.05 * len(vals)):
        return "categorical"
    if distinct > 0.9 * len(vals):
        return "text" if avg_words >= 2 else "skip"  # unique short strings carry no context
    return "categorical"


def profiles(graph: Graph, table: str) -> dict[str, Profile]:
    cache: dict[str, dict[str, Profile]] = graph.__dict__.setdefault("_score_profiles", {})
    if table in cache:
        return cache[table]
    rows, keys = graph.table_rows(table), graph.key_fields(table)
    out: dict[str, Profile] = {}
    for col in graph.fields(table):
        values = [r.get(col) for r in rows]
        p = Profile(col, classify(col, values, col in keys), len(rows))
        if p.kind in ("identifier", "categorical"):
            p.value_df = Counter(str(v) for v in values if v not in (None, ""))
        elif p.kind == "date":
            p.value_df = Counter(str(v)[:7] for v in values if v not in (None, ""))
        elif p.kind == "text":
            for v in values:
                if v not in (None, ""):
                    p.token_df.update(set(_tokens(v)))
        elif p.kind == "numeric":
            nums = [x for x in (_num(v) for v in values) if x is not None]
            if nums:
                p.mean = sum(nums) / len(nums)
                p.std = math.sqrt(sum((x - p.mean) ** 2 for x in nums) / len(nums))
        out[col] = p
    cache[table] = out
    return out


def _idf(df: int, n: int) -> float:
    """1 for a value only one row has, close to 0 for a value every row has."""
    return 1.0 if n <= 1 else max(0.0, math.log((1 + n) / (1 + df)) / math.log(1 + n))


@dataclass
class Occurrence:
    database: str
    table: str
    column: str
    step: int
    path: list[str]
    weight: float


@dataclass
class Term:
    key: str
    display: str
    kind: str
    weight: float
    query_match: bool
    occurrence: Occurrence


def _norm(text: str) -> str:
    return re.sub(r"[_.\-/]+", " ", str(text).lower())


def _matches(text: str, keywords: list[str]) -> bool:
    """A keyword (or phrase, or stem such as 'refrigerat') starting a word of `text`."""
    t = _norm(text)
    return any(re.search(r"\b" + re.escape(_norm(k)), t) for k in keywords if len(k) >= 3)


def extract_terms(
    graph: Graph, db_id: str, table: str, rows: list[dict[str, Any]], step: int, path: list[str],
    keywords: list[str], params: dict[str, Any],
) -> list[Term]:  # fmt: skip
    if not rows:
        return []
    prof, n_res, decay = profiles(graph, table), len(rows), params["decay"] ** step
    out: list[Term] = []

    def add(key: str, display: str, kind: str, tf: float, idf: float, col: str) -> None:
        qm = _matches(display, keywords) or _matches(col, keywords)
        w = tf * (0.05 + idf) * KIND_WEIGHT[kind] * decay * (1 + params["query_boost"] * qm)
        out.append(
            Term(key, display, kind, round(w, 5), qm, Occurrence(db_id, table, col, step, path, round(w, 5)))
        )

    for col, p in prof.items():
        if p.kind == "skip":
            continue
        if p.kind in ("identifier", "categorical", "date"):
            groups: dict[str, int] = defaultdict(int)
            for r in rows:
                v = r.get(col)
                if v not in (None, ""):
                    groups[str(v)[:7] if p.kind == "date" else str(v)] += 1
            for v, count in groups.items():
                key = f"id:{v.strip().upper()}" if p.kind == "identifier" else f"{p.kind}:{col}={v.lower()}"
                display = v if p.kind == "identifier" else f"{col}={v}"
                add(key, display, p.kind, count / n_res, _idf(p.value_df.get(v, 0), p.n_rows), col)
        elif p.kind == "text":
            holders: dict[str, int] = defaultdict(int)
            for r in rows:
                if r.get(col) not in (None, ""):
                    for t in set(_tokens(r[col])):
                        holders[t] += 1
            for t, count in holders.items():
                add(f"word:{t}", t, "text", count / n_res, _idf(p.token_df.get(t, 0), p.n_rows), col)
        elif p.kind == "numeric":
            xs = [x for x in (_num(r.get(col)) for r in rows) if x is not None]
            if not xs:
                continue
            mean = sum(xs) / len(xs)
            z = abs(mean - p.mean) / (p.std + 1e-9) if p.std else 0.0
            display = (
                f"{col} {min(xs):g}..{max(xs):g} (table mean {p.mean:.4g})" if len(xs) > 1
                else f"{col}={xs[0]:g} (table mean {p.mean:.4g})"
            )  # fmt: skip
            add(f"num:{table}.{col}", display, "numeric", 1.0, min(1.0, z / 2.0), col)
    return out


def _affinity(graph: Graph, table: str, keywords: list[str]) -> float:
    """1.0 when the neighbouring table's name matches the question, 0.5 when only a column does."""
    if _matches(table, keywords):
        return 1.0
    return 0.5 if any(_matches(c, keywords) for c in graph.fields(table)) else 0.0


def step_label(edge: Edge, from_table: str) -> str:
    """One join, written in the direction it was walked."""
    if edge.child == from_table:
        return (
            f"{edge.child}({', '.join(edge.child_fields)}) -> {edge.parent}({', '.join(edge.parent_fields)})"
        )
    return f"{edge.parent}({', '.join(edge.parent_fields)}) -> {edge.child}({', '.join(edge.child_fields)})"


def discover(
    graph: Graph, db_id: str, target: str, seed_rows: list[dict[str, Any]], keywords: list[str],
    params: dict[str, Any] | None = None, extra_seeds: list[tuple[str, list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:  # fmt: skip
    p = {**DEFAULTS, **(params or {})}
    kws = [k.lower() for k in keywords if k]
    context: dict[str, dict[str, Any]] = {}

    def merge(terms: list[Term]) -> None:
        for t in terms:
            c = context.get(t.key)
            if c is None:
                context[t.key] = {"key": t.key, "term": t.display, "kind": t.kind, "score": t.weight,
                                  "query_match": t.query_match, "best": t.occurrence, "occurrences": [t.occurrence]}  # fmt: skip
                continue
            c["occurrences"].append(t.occurrence)
            c["query_match"] = c["query_match"] or t.query_match
            if t.weight > c["best"].weight:
                c["best"], c["term"] = t.occurrence, t.display
            ws = sorted((o.weight for o in c["occurrences"]), reverse=True)
            c["score"] = round(
                ws[0] + 0.25 * sum(ws[1:]), 5
            )  # repeated evidence counts, with diminishing returns

    seeds = [(target, seed_rows), *[s for s in (extra_seeds or []) if s[0] != target]]
    relations: list[dict[str, Any]] = []
    for table, rows in seeds:  # more than one table can mention the pack (a receipt line and a dispatch line)
        merge(extract_terms(graph, db_id, table, rows, 0, [], kws, p))
        relations.append({"table": table, "rows": rows, "step": 0, "path": []})
    explored, evaluated = {table for table, _ in seeds}, {}
    steps: list[dict[str, Any]] = []
    joins: list[dict[str, Any]] = []
    stop = f"reached MAX_AUGMENTATION = {p['max_augmentation']}"
    for step in range(1, p["max_augmentation"] + 1):
        candidates: list[dict[str, Any]] = []
        for rel in relations:
            for edge in graph.edges:
                if rel["table"] not in (edge.child, edge.parent) or edge.child == edge.parent:
                    continue
                other = edge.parent if edge.child == rel["table"] else edge.child
                if other in explored:
                    continue
                key = (rel["table"], edge.label)
                if key not in evaluated:
                    _o, joined, native, total = graph.join(edge, rel["table"], rel["rows"], p["join_cap"])
                    terms = extract_terms(graph, db_id, other, joined, rel["step"] + 1,
                                          [*rel["path"], step_label(edge, rel["table"])], kws, p)  # fmt: skip
                    evaluated[key] = {"edge": edge, "from": rel["table"], "to": other, "rows": joined,
                                      "native": native, "total": total, "terms": terms, "rel": rel}  # fmt: skip
                ev = evaluated[key]
                new = sorted((t.weight for t in ev["terms"] if t.key not in context), reverse=True)
                gain, aff = sum(new[: p["gain_top_k"]]), _affinity(graph, other, kws)
                fanout = len(ev["rows"]) / max(1, len(rel["rows"]))
                penalty = 1.0 / (1.0 + math.log2(max(1.0, fanout)))
                score = round(gain * (1 + p["affinity_boost"] * aff) * penalty, 5) if ev["rows"] else 0.0
                candidates.append({"fk": step_label(ev["edge"], ev["from"]), "kind": ev["edge"].kind, "from": ev["from"],
                                   "to": other, "joined_rows": len(ev["rows"]), "new_terms": len(new),
                                   "schema_affinity": aff, "fanout": round(fanout, 2), "fk_relevance": score, "_key": key})  # fmt: skip
        if not candidates:
            stop = "no unexplored neighbouring table"
            break
        candidates.sort(key=lambda c: (-c["fk_relevance"], c["fk"]))
        best = candidates[0]
        public = [{k: v for k, v in c.items() if k != "_key"} for c in candidates]
        if best["fk_relevance"] < p["min_fk_relevance"]:
            steps.append({"step": step, "candidates": public, "chosen": None})
            stop = (f"no neighbouring table adds relevant context (best relevance {best['fk_relevance']} "
                    f"< MIN_FK_RELEVANCE {p['min_fk_relevance']})")  # fmt: skip
            break
        ev = evaluated[best["_key"]]
        merge(ev["terms"])
        explored.add(ev["to"])
        relations.append({"table": ev["to"], "rows": ev["rows"], "step": ev["rel"]["step"] + 1,
                          "path": [*ev["rel"]["path"], step_label(ev["edge"], ev["from"])]})  # fmt: skip
        joins.append({"step": step, "fk": step_label(ev["edge"], ev["from"]), "from": ev["from"], "to": ev["to"],
                      "join": ev["native"], "joined_rows": len(ev["rows"]), "fk_relevance": best["fk_relevance"]})  # fmt: skip
        steps.append({"step": step, "candidates": public, "chosen": best["fk"]})
    ranked = sorted(context.values(), key=lambda c: (-c["score"], c["key"]))[: p["top_n"]]
    return {
        "algorithm": "SCORE-inspired query context (tf x idf terms, greedy foreign-key augmentation)",
        "parameters": {
            k: p[k] for k in ("max_augmentation", "top_n", "decay", "min_fk_relevance", "join_cap")
        },
        "keywords": kws,
        "query_result": {"tables": {table: len(rows) for table, rows in seeds}},
        "augmentation": steps,
        "stop_reason": stop,
        "explored_tables": [r["table"] for r in relations],
        "joins_performed": joins,
        "ranked_context": [
            {
                "term": c["term"],
                "key": c["key"],
                "kind": c["kind"],
                "score": c["score"],
                "query_match": c["query_match"],
                "source": {"table": c["best"].table, "column": c["best"].column},
                "relationship_path": c["best"].path or ["(query result)"],
                "step": c["best"].step,
            }
            for c in ranked
        ],  # fmt: skip
    }
