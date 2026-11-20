"""
score_context.py
----------------
SCORE-inspired query-context discovery, run by ONE database on its own schema
and records (Phase 3).

SCORE (Week-11 L1) associates a structured query with context drawn from the
database itself: the query's result relation says what the query is about, and
the tables next to it, reached through foreign keys, say more. This module
implements those ideas for one source:

  1. QUERY RESULT     Execute the subquery; keep the whole result relation R0,
                      every column, not only a projection.
  2. SCHEMA GRAPH     Tables are nodes, FK-PK relationships edges, read from
                      the database itself (PRAGMA foreign_key_list / the DB1
                      document-reference manifest). Nothing is hard-coded.
  3. TERMS            Candidate context terms are extracted from R0, per column
                      kind: words of text attributes, categorical values,
                      identifiers, dates (month), and numeric attributes (one
                      summary term per column). Each term is weighted by
                          w = tf_R  x  idf_T  x  kind weight  [x query boost]
                      tf_R  = share of result rows holding the term,
                      idf_T = how rare the term is in that column over the
                              whole table (log-scaled to 0..1),
                      so a value that is common in the result but rare in the
                      database (cold_chain_maintained = 0) outranks one every
                      row has (currency = INR). Numeric columns are scored by
                      how far the result's mean sits from the table's mean.
  4. AUGMENTATION     Greedy, as in SCORE: for every FK edge from an explored
                      table to an unexplored one, perform the join from the
                      current relation, extract the joined records' terms and
                      compute the FK's relevance
                          rel = (sum of the 5 best NEW term weights)
                                x schema affinity   (table/column names that
                                                     match the query's words)
                                x fan-out penalty   1 / (1 + log2(rows per source row))
                      Join the single most relevant FK, add its terms (decayed
                      by DECAY per augmentation step), and repeat, until
                      MAX_AUGMENTATION joins or no FK reaches MIN_FK_RELEVANCE.
                      An FK whose join adds nothing new scores 0 and is never
                      followed, however available it is.
  5. RANKING          Terms are merged by key, scored, and the TOP_N returned
                      with provenance: database, table, column, FK path, and
                      the identifiers of the rows they came from.

Interpretations made here (the lecture's exact formulas were not available when
this was written): the tf x idf weighting, the top-5 gain, the affinity and
fan-out factors, and the default parameter values. All are parameters.

This is query context discovery, not entity matching: entity matching (the
`code` operator, Phase 2) only decides which rows form R0; everything here
starts from R0.
"""

from __future__ import annotations
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from integration.federation.query_parser import STOPWORDS
from integration.uncertainty.standardize import canonical_code

DEFAULTS = {
    "max_augmentation": 4,       # FK joins at most
    "top_n": 20,                 # context terms returned
    "decay": 0.7,                # weight multiplier per augmentation step
    "min_fk_relevance": 0.05,    # below this a neighbouring table is not worth joining
    "join_cap": 200,             # rows read per join
    "query_boost": 1.0,          # extra weight for a term that matches the query's words
    "affinity_boost": 1.0,       # extra FK relevance when the table/columns match the query's words
    "gain_top_k": 5,
}
KIND_WEIGHT = {"text": 1.0, "identifier": 0.9, "categorical": 0.8, "numeric": 0.6, "date": 0.5}
SKIP_NAME = re.compile(r"(hash|image|url|email|phone|password|token|firmware|contact)", re.I)
ID_NAME = re.compile(r"(_id|_ref|_uid|_no|^_id$|registration|license|licence|code|serial|batch_number|number)$", re.I)
DATE_NAME = re.compile(r"(date|_on$|_at$|timestamp|expiry|since|until|time)", re.I)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
WORD = re.compile(r"[a-z][a-z0-9+\-]{2,}")


# -- column profiles (computed once per table and cached on the engine) ----------------

@dataclass
class Profile:
    column: str
    kind: str                     # text / identifier / categorical / numeric / date / skip
    n_rows: int
    value_df: Counter = field(default_factory=Counter)
    token_df: Counter = field(default_factory=Counter)
    mean: float = 0.0
    std: float = 0.0


def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _tokens(v) -> List[str]:
    return [t for t in WORD.findall(str(v).lower()) if t not in STOPWORDS]


def classify(column: str, values: List[Any], is_key: bool) -> str:
    vals = [v for v in values if v not in (None, "")]
    if not vals or SKIP_NAME.search(column):
        return "skip"
    if is_key:
        return "identifier"
    nums = [_num(v) for v in vals]
    distinct = len(set(map(str, vals)))
    if all(n is not None for n in nums):
        return "categorical" if distinct <= 2 else ("identifier" if ID_NAME.search(column) else "numeric")
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
        return "text" if avg_words >= 2 else "skip"     # unique short strings carry no context
    return "categorical"


def profiles(engine, table: str) -> Dict[str, Profile]:
    cache = engine.__dict__.setdefault("_score_profiles", {})
    if table in cache:
        return cache[table]
    rows = engine.table_rows(table)
    keys = engine.key_fields(table)
    out = {}
    for col in engine.fields(table):
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
            nums = [_num(v) for v in values if _num(v) is not None]
            if nums:
                p.mean = sum(nums) / len(nums)
                p.std = math.sqrt(sum((x - p.mean) ** 2 for x in nums) / len(nums))
        out[col] = p
    cache[table] = out
    return out


def _idf(df: int, n: int) -> float:
    """0..1: 1 for a value only this row has, ~0 for a value every row has."""
    if n <= 1:
        return 1.0
    return max(0.0, math.log((1 + n) / (1 + df)) / math.log(1 + n))


# -- terms ------------------------------------------------------------------------------

@dataclass
class Occurrence:
    database: str
    table: str
    column: str
    step: int
    path: List[str]
    weight: float
    entities: List[Dict[str, Any]]


@dataclass
class Term:
    key: str
    display: str
    kind: str
    weight: float
    query_match: bool
    occurrence: Occurrence


def _norm(text: str) -> str:
    """'cold_chain_maintained' and 'Cold-chain' both read as 'cold chain ...'."""
    return re.sub(r"[_.\-/]+", " ", str(text).lower())


def _matches_query(text: str, keywords: List[str]) -> bool:
    """A keyword (or phrase, or stem such as 'refrigerat') starting a word of `text`.
    Phrases stay whole: 'cold chain' matches 'cold_chain_maintained', not 'Supply Chain'."""
    t = _norm(text)
    return any(re.search(r"\b" + re.escape(_norm(k)), t) for k in keywords if len(k) >= 3)


def extract_terms(engine, db_id: str, table: str, rows: List[Dict[str, Any]], step: int, path: List[str],
                  keywords: List[str], params: Dict[str, Any], bridge: Dict[str, str]) -> List[Term]:
    if not rows:
        return []
    prof = profiles(engine, table)
    n_res = len(rows)
    decay = params["decay"] ** step
    out: List[Term] = []

    def entities_of(sel_rows):
        ents = []
        for r in sel_rows[:5]:
            e = dict(engine.pk_dict(table, r))
            for fld, concept in bridge.items():
                if r.get(fld) not in (None, ""):
                    e[concept] = canonical_code(str(r[fld])) if concept == "item_code" else r[fld]
            ents.append(e)
        return ents

    def add(key, display, kind, tf, idf, col, holders):
        qm = _matches_query(display, keywords) or _matches_query(col, keywords)
        w = tf * (0.05 + idf) * KIND_WEIGHT[kind] * decay * (1 + params["query_boost"] * qm)
        out.append(Term(key, display, kind, round(w, 5), qm,
                        Occurrence(db_id, table, col, step, path, round(w, 5), entities_of(holders))))

    for col, p in prof.items():
        if p.kind == "skip":
            continue
        if p.kind in ("identifier", "categorical", "date"):
            groups = defaultdict(list)
            for r in rows:
                v = r.get(col)
                if v in (None, ""):
                    continue
                groups[str(v)[:7] if p.kind == "date" else str(v)].append(r)
            for v, holders in groups.items():
                if p.kind == "identifier":
                    key = f"id:{canonical_code(v) if 'MED' in v.upper() else v.strip().upper()}"
                    display = v
                else:
                    key = f"{p.kind}:{col}={v.lower()}"
                    display = f"{col}={v}"
                add(key, display, p.kind, len(holders) / n_res, _idf(p.value_df.get(v, 0), p.n_rows), col, holders)
        elif p.kind == "text":
            holders_by_tok = defaultdict(list)
            for r in rows:
                if r.get(col) not in (None, ""):
                    for t in set(_tokens(r[col])):
                        holders_by_tok[t].append(r)
            for t, holders in holders_by_tok.items():
                add(f"word:{t}", t, "text", len(holders) / n_res, _idf(p.token_df.get(t, 0), p.n_rows), col, holders)
        elif p.kind == "numeric":
            nums = [(_num(r.get(col)), r) for r in rows if _num(r.get(col)) is not None]
            if not nums:
                continue
            xs = [x for x, _r in nums]
            mean = sum(xs) / len(xs)
            z = abs(mean - p.mean) / (p.std + 1e-9) if p.std else 0.0
            display = (f"{col} {min(xs):g}..{max(xs):g} (mean {mean:.4g}; table mean {p.mean:.4g})"
                       if len(xs) > 1 else f"{col}={xs[0]:g} (table mean {p.mean:.4g})")
            add(f"num:{table}.{col}", display, "numeric", 1.0, min(1.0, z / 2.0), col, [r for _x, r in nums])
    return out


# -- FK augmentation -------------------------------------------------------------------------

def _affinity(engine, table: str, keywords: List[str]) -> float:
    """How much the neighbouring table is ABOUT the query: 1.0 when its name matches
    a query word or phrase, 0.5 when only one of its columns does, else 0."""
    if _matches_query(table, keywords):
        return 1.0
    return 0.5 if any(_matches_query(c, keywords) for c in engine.fields(table)) else 0.0


def discover(engine, db_id: str, target: str, seed_rows: List[Dict[str, Any]], keywords: List[str],
             bridge_spec: Dict[str, Dict[str, str]], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = {**DEFAULTS, **(params or {})}
    keywords = [k.lower() for k in keywords if k]
    graph = {"nodes": sorted(engine.tables), "edges": [
        {"label": e.label, "child": e.child, "child_columns": list(e.child_fields), "parent": e.parent,
         "parent_columns": list(e.parent_fields), "kind": e.kind} for e in engine.edges]}

    context: Dict[str, Dict[str, Any]] = {}

    def merge(terms: List[Term]):
        for t in terms:
            c = context.get(t.key)
            if c is None:
                context[t.key] = {"key": t.key, "term": t.display, "kind": t.kind, "score": t.weight,
                                  "query_match": t.query_match, "best": t.occurrence, "occurrences": [t.occurrence]}
            else:
                c["occurrences"].append(t.occurrence)
                c["query_match"] = c["query_match"] or t.query_match
                if t.weight > c["best"].weight:
                    c["best"], c["term"] = t.occurrence, t.display
                # repeated evidence counts, with diminishing returns
                c["score"] = round(max(o.weight for o in c["occurrences"]) +
                                   0.25 * sum(sorted((o.weight for o in c["occurrences"]), reverse=True)[1:]), 5)

    r0_terms = extract_terms(engine, db_id, target, seed_rows, 0, [], keywords, params, bridge_spec.get(target, {}))
    merge(r0_terms)
    relations = [{"table": target, "rows": seed_rows, "step": 0, "path": []}]
    explored = {target}
    evaluated: Dict[Tuple[str, str], Dict[str, Any]] = {}
    steps, joins = [], []
    stop_reason = f"reached MAX_AUGMENTATION = {params['max_augmentation']}"

    for step in range(1, params["max_augmentation"] + 1):
        candidates = []
        for rel in relations:
            for edge in engine.edges:
                if rel["table"] not in (edge.child, edge.parent) or edge.child == edge.parent:
                    continue
                other = edge.parent if edge.child == rel["table"] else edge.child
                if other in explored:
                    continue
                key = (rel["table"], edge.label)
                if key not in evaluated:
                    _o, joined, native, total = engine.join(edge, rel["table"], rel["rows"], params["join_cap"])
                    terms = extract_terms(engine, db_id, other, joined, rel["step"] + 1, rel["path"] + [edge.label],
                                          keywords, params, bridge_spec.get(other, {}))
                    evaluated[key] = {"edge": edge, "from": rel["table"], "to": other, "rows": joined,
                                      "native": native, "total": total, "terms": terms, "rel": rel}
                ev = evaluated[key]
                new = sorted((t.weight for t in ev["terms"] if t.key not in context), reverse=True)
                gain = sum(new[:params["gain_top_k"]])
                aff = _affinity(engine, other, keywords)
                fanout = len(ev["rows"]) / max(1, len(rel["rows"]))
                penalty = 1.0 / (1.0 + math.log2(max(1.0, fanout)))
                score = round(gain * (1 + params["affinity_boost"] * aff) * penalty, 5) if ev["rows"] else 0.0
                candidates.append({"step": step, "fk": ev["edge"].label, "kind": ev["edge"].kind,
                                   "direction": "to referenced (PK) table" if ev["edge"].child == ev["from"]
                                   else "to referencing (FK) table",
                                   "from": ev["from"], "to": other, "joined_rows": len(ev["rows"]),
                                   "rows_matching_join": ev["total"], "new_terms": len(new),
                                   "top_new_terms": [t.display for t in sorted(ev["terms"], key=lambda t: -t.weight)
                                                     if t.key not in context][:4],
                                   "schema_affinity": aff, "fanout": round(fanout, 2),
                                   "relevance_formula": f"gain {gain:.3f} x (1 + {params['affinity_boost']} x affinity "
                                                        f"{aff}) x fan-out penalty {penalty:.3f}",
                                   "fk_relevance": score, "_key": key})
        if not candidates:
            stop_reason = "no unexplored neighbouring table"
            break
        candidates.sort(key=lambda c: (-c["fk_relevance"], c["fk"]))
        best = candidates[0]
        public = [{k: v for k, v in c.items() if k != "_key"} for c in candidates]
        if best["fk_relevance"] < params["min_fk_relevance"]:
            steps.append({"step": step, "candidates": public, "chosen": None})
            stop_reason = (f"no neighbouring table adds relevant context (best FK relevance "
                           f"{best['fk_relevance']} < MIN_FK_RELEVANCE {params['min_fk_relevance']})")
            break
        ev = evaluated[best["_key"]]
        for c in public:
            c["chosen"] = c["fk"] == best["fk"] and c["from"] == best["from"]
        merge(ev["terms"])
        explored.add(ev["to"])
        relations.append({"table": ev["to"], "rows": ev["rows"], "step": ev["rel"]["step"] + 1,
                          "path": ev["rel"]["path"] + [ev["edge"].label]})
        joins.append({"step": step, "fk": ev["edge"].label, "from": ev["from"], "to": ev["to"],
                      "join": ev["native"], "joined_rows": len(ev["rows"]), "fk_relevance": best["fk_relevance"]})
        steps.append({"step": step, "candidates": public, "chosen": best["fk"]})

    ranked = sorted(context.values(), key=lambda c: (-c["score"], c["key"]))[:params["top_n"]]

    def occ(o: Occurrence) -> Dict[str, Any]:
        return {"database": o.database, "table": o.table, "column": o.column, "augmentation_step": o.step,
                "relationship_path": o.path or ["(query result)"], "weight": o.weight, "entities": o.entities}

    additional = [{"table": r["table"], "augmentation_step": r["step"], "relationship_path": r["path"],
                   "pk": engine.pk_dict(r["table"], row)}
                  for r in relations[1:] for row in r["rows"]]
    return {
        "algorithm": "SCORE-inspired query context (tf x idf terms, greedy FK augmentation)",
        "parameters": {k: params[k] for k in ("max_augmentation", "top_n", "decay", "min_fk_relevance", "join_cap")},
        "keywords": keywords,
        "schema_graph": graph,
        "query_result": {"table": target, "rows": len(seed_rows), "columns": list(engine.fields(target)),
                         "column_kinds": {c: p.kind for c, p in profiles(engine, target).items()}},
        "result_terms": [{"term": t.display, "kind": t.kind, "column": t.occurrence.column, "weight": t.weight,
                          "query_match": t.query_match}
                         for t in sorted(r0_terms, key=lambda t: -t.weight)[:12]],
        "augmentation": steps,
        "stop_reason": stop_reason,
        "explored_tables": [r["table"] for r in relations],
        "joins_performed": joins,
        "additional_records": additional,
        "ranked_context": [{"term": c["term"], "key": c["key"], "kind": c["kind"], "score": c["score"],
                            "query_match": c["query_match"],
                            "source": {"database": c["best"].database, "table": c["best"].table,
                                       "column": c["best"].column},
                            "relationship_path": c["best"].path or ["(query result)"],
                            "entities": c["best"].entities, "occurrences": [occ(o) for o in c["occurrences"]][:6]}
                           for c in ranked],
    }
