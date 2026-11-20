"""
local_engine.py
---------------
The part of Phase 3 that runs ON a database's own machine, against that
database only. It does three things:

1. Executes a subquery. A subquery is declarative JSON, not SQL text:

       {"id": "Q1.db2.1", "target": "distribution_batches",
        "where": [{"field": "batch_serial", "op": "code", "value": "MED-ASALI-009"}],
        "combine": "all", "limit": 25,
        "expand": {"max_hops": 2, "row_budget": 120, "terms": ["cold", "chain"]}}

   Every table/collection and field name is checked against this database's own
   schema before anything runs, so a caller cannot inject SQL. The engine compiles
   the subquery into the source's native language: parameterised SQL for the
   SQLite sources, a document filter over the JSON collections for DB1. The
   native query is returned with the rows.

2. Discovers local context. From the rows the subquery matched, it walks this
   database's own FK-PK graph (PRAGMA foreign_key_list for SQLite, the declared
   document references for DB1) breadth-first, in both directions, scoring every
   row it reaches by hop distance, fan-out and overlap with the query terms.

3. Reports bridge keys: the business identifiers found in those rows that other
   databases also hold (item code, vendor, distributor, manufacturer, dispatch
   reference). The coordinator uses them; this engine never contacts another
   database.

Operators: eq, in, contains, contains_any, gte, lte, and code. `code` matches a
medicine code the way Phase 2 taught the system to: exact, then formatting-only
differences (canonical_code), then scanner look-alike characters (O/0, I/1, ...),
then one edit, each labelled with its match type and score.
"""

from __future__ import annotations
import json
import math
import os
import re
import sqlite3
import threading
from contextlib import closing
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from integration.uncertainty import paths
from integration.uncertainty.context import fold
from integration.uncertainty.similarity import damerau_osa
from integration.uncertainty.standardize import canonical_code
from integration.federation import nosql_store, schema_catalog

MAPPING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema_mapping.json")
OPS = {"eq", "in", "contains", "contains_any", "gte", "lte", "code"}
MATCH_SCORE = {"exact": 1.0, "tidied": 0.97, "lookalike": 0.9, "one_edit": 0.6, "filter": 1.0}
HOP_DECAY = 0.6
MIN_SCORE = 0.04


class SubqueryError(ValueError):
    """A subquery that does not fit this database's schema (HTTP 400)."""


def _mapping() -> Dict[str, Any]:
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("phase3", {})


# -- code matching (Phase 2 standardisation, local values only) -----------------

def code_matches(query: str, values: Iterable[str]) -> Dict[str, Tuple[str, float]]:
    """stored value -> (match type, score) for every stored value that matches `query`."""
    q = canonical_code(query)
    qf = fold(q)
    best: Dict[str, Tuple[str, float]] = {}
    one_edit: Dict[str, Tuple[str, float]] = {}
    for v in values:
        if v is None:
            continue
        s = str(v)
        c = canonical_code(s)
        if s == query:
            best[s] = ("exact", MATCH_SCORE["exact"])
        elif c == q:
            best[s] = ("tidied", MATCH_SCORE["tidied"])
        elif fold(c) == qf:
            best[s] = ("lookalike", MATCH_SCORE["lookalike"])
        elif abs(len(c) - len(q)) <= 1 and damerau_osa(c, q) == 1:
            one_edit[s] = ("one_edit", MATCH_SCORE["one_edit"])
    # one edit away is only offered when nothing closer exists: Phase 1 showed that
    # loose matching on structured codes otherwise links fakes to real products
    return best or one_edit


# -- execution engines -----------------------------------------------------------

@dataclass
class Edge:
    label: str
    child: str
    child_fields: Tuple[str, ...]
    parent: str
    parent_fields: Tuple[str, ...]
    kind: str = "foreign_key"     # or document_reference / business_key_lookup
    weight: float = 1.0


class SqlEngine:
    """A SQLite source: DB2, DB3, DB4 (and DB1's authoritative tables)."""
    paradigm = "relational"

    def __init__(self, db_id: str, db_path: str):
        self.db_id, self.db_path = db_id, db_path
        self.tables = schema_catalog.describe(db_path)
        self.edges = [Edge(fk.label(), fk.table, fk.columns, fk.ref_table, fk.ref_columns)
                      for t in self.tables.values() for fk in t.foreign_keys]
        self.queries: List[str] = []
        self._distinct: Dict[Tuple[str, str], List[str]] = {}

    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    def fields(self, target: str) -> List[str]:
        return self.tables[target].columns

    def pk(self, target: str, row: Dict[str, Any]) -> Tuple:
        cols = self.tables[target].primary_key or self.tables[target].columns[:1]
        return tuple(row.get(c) for c in cols)

    def pk_dict(self, target: str, row: Dict[str, Any]) -> Dict[str, Any]:
        cols = self.tables[target].primary_key or self.tables[target].columns[:1]
        return {c: row.get(c) for c in cols}

    def distinct(self, target: str, fld: str) -> List[str]:
        key = (target, fld)
        if key not in self._distinct:
            with closing(self.conn()) as c:
                self._distinct[key] = [r[0] for r in c.execute(
                    f'SELECT DISTINCT "{fld}" FROM "{target}" WHERE "{fld}" IS NOT NULL')]
        return self._distinct[key]

    def select(self, target: str, where: List[Dict[str, Any]], combine: str, limit: int):
        clauses, params, match_info = [], [], {}
        for cond in where:
            fld, op, val = cond["field"], cond["op"], cond.get("value")
            col = f'"{fld}"'
            if op == "eq":
                clauses.append(f"{col} = ?"); params.append(val)
            elif op == "in":
                vals = list(val or [])
                clauses.append(f"{col} IN ({','.join('?' * len(vals)) or 'NULL'})"); params.extend(vals)
            elif op == "contains":
                clauses.append(f"LOWER({col}) LIKE ?"); params.append(f"%{str(val).lower()}%")
            elif op == "contains_any":
                vals = [str(v).lower() for v in (val or [])]
                clauses.append("(" + " OR ".join(f"LOWER({col}) LIKE ?" for _ in vals) + ")" if vals else "0")
                params.extend(f"%{v}%" for v in vals)
            elif op == "gte":
                clauses.append(f"{col} >= ?"); params.append(val)
            elif op == "lte":
                clauses.append(f"{col} <= ?"); params.append(val)
            elif op == "code":
                hits = code_matches(str(val), self.distinct(target, fld))
                match_info.update({(fld, k): v for k, v in hits.items()})
                vals = list(hits)
                clauses.append(f"{col} IN ({','.join('?' * len(vals)) or 'NULL'})"); params.extend(vals)
        joiner = " AND " if combine == "all" else " OR "
        sql = f'SELECT * FROM "{target}"' + (f" WHERE {joiner.join(clauses)}" if clauses else "") + " LIMIT ?"
        params.append(int(limit))
        with closing(self.conn()) as c:
            rows = [dict(r) for r in c.execute(sql, params)]
        self.queries.append(sql)
        out = []
        for r in rows:
            m = [match_info[(cond["field"], str(r.get(cond["field"])))] for cond in where
                 if cond["op"] == "code" and (cond["field"], str(r.get(cond["field"]))) in match_info]
            mt, sc = min(m, key=lambda x: x[1]) if m else ("filter", 1.0)
            out.append((r, mt, sc))
        return out, sql, params

    def follow(self, edge: Edge, table: str, row: Dict[str, Any], cap: int):
        """Rows one FK hop away from `row` along `edge` (in whichever direction applies)."""
        if edge.child == table:            # child -> parent
            other, mine, theirs = edge.parent, edge.child_fields, edge.parent_fields
        else:                              # parent -> children
            other, mine, theirs = edge.child, edge.parent_fields, edge.child_fields
        vals = [row.get(c) for c in mine]
        if any(v is None for v in vals):
            return other, [], 0
        cond = " AND ".join(f'"{c}" = ?' for c in theirs)
        with closing(self.conn()) as c:
            n = c.execute(f'SELECT COUNT(*) FROM "{other}" WHERE {cond}', vals).fetchone()[0]
            rows = [dict(r) for r in c.execute(f'SELECT * FROM "{other}" WHERE {cond} LIMIT ?', vals + [cap])] if n else []
        self.queries.append(f'SELECT * FROM "{other}" WHERE {cond}')
        return other, rows, n

    def native(self, sql: str, params: List[Any]) -> str:
        return sql

    def schema(self) -> Dict[str, Any]:
        return {"paradigm": "relational (SQLite)",
                "tables": {n: {"rows": t.rows, "primary_key": t.primary_key, "columns": t.columns,
                               "unique_keys": t.unique_keys} for n, t in self.tables.items()},
                "relationships": [{"kind": "foreign_key", "child": e.child, "child_columns": list(e.child_fields),
                                   "parent": e.parent, "parent_columns": list(e.parent_fields), "label": e.label}
                                  for e in self.edges]}


def _flatten(doc: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


class DocEngine:
    """DB1's JSON document collections (the NoSQL side of the retail POS)."""
    paradigm = "document"

    def __init__(self, store_dir: str):
        self.db_id, self.store_dir = "db1", store_dir
        names = list(nosql_store.COLLECTIONS) + [nosql_store.SCAN_COLLECTION]
        self.docs = {c: nosql_store.load(store_dir, c) for c in names}
        self.flat = {c: [_flatten(d) for d in docs] for c, docs in self.docs.items()}
        self.field_sets = {c: sorted({k for d in flat for k in d}) for c, flat in self.flat.items()}
        self.by_id = {c: {d.get("_id"): i for i, d in enumerate(docs)} for c, docs in self.docs.items()}
        self.edges = [Edge(f"{c}.{f} -> {t}._id", c, (f,), t, ("_id",), kind=k,
                           weight=1.0 if k == "document_reference" else 0.8)
                      for c, f, t, k in nosql_store.REFERENCES]
        self.queries: List[str] = []

    @property
    def tables(self):
        return self.docs

    def fields(self, target: str) -> List[str]:
        return self.field_sets[target]

    def pk(self, target, row):
        return (row.get("_id"),)

    def pk_dict(self, target, row):
        return {"_id": row.get("_id")}

    def distinct(self, target, fld):
        return list({d.get(fld) for d in self.flat[target] if d.get(fld) is not None})

    def select(self, target, where, combine, limit):
        match_info, tests, mongo = {}, [], {}
        for cond in where:
            fld, op, val = cond["field"], cond["op"], cond.get("value")
            if op == "code":
                hits = code_matches(str(val), self.distinct(target, fld))
                match_info.update({(fld, k): v for k, v in hits.items()})
                keys = set(hits)
                tests.append(lambda d, f=fld, ks=keys: str(d.get(f)) in ks)
                mongo[fld] = {"$in": sorted(keys)}
            elif op == "eq":
                tests.append(lambda d, f=fld, v=val: d.get(f) == v); mongo[fld] = v
            elif op == "in":
                vs = set(val or []); tests.append(lambda d, f=fld, vs=vs: d.get(f) in vs); mongo[fld] = {"$in": sorted(map(str, vs))}
            elif op in ("contains", "contains_any"):
                vs = [str(v).lower() for v in ([val] if op == "contains" else (val or []))]
                tests.append(lambda d, f=fld, vs=vs: any(v in str(d.get(f) or "").lower() for v in vs))
                mongo[fld] = {"$regex": "|".join(map(re.escape, vs)), "$options": "i"}
            elif op == "gte":
                tests.append(lambda d, f=fld, v=val: d.get(f) is not None and str(d.get(f)) >= str(v)); mongo[fld] = {"$gte": val}
            elif op == "lte":
                tests.append(lambda d, f=fld, v=val: d.get(f) is not None and str(d.get(f)) <= str(v)); mongo[fld] = {"$lte": val}
        combinator = all if combine == "all" else any
        native = f"db.{target}.find({json.dumps(mongo if combine == 'all' else {'$or': [{k: v} for k, v in mongo.items()]})}).limit({int(limit)})"
        out = []
        for doc, flat in zip(self.docs[target], self.flat[target]):
            if not tests or combinator(t(flat) for t in tests):
                m = [match_info[(c["field"], str(flat.get(c["field"])))] for c in where
                     if c["op"] == "code" and (c["field"], str(flat.get(c["field"]))) in match_info]
                mt, sc = min(m, key=lambda x: x[1]) if m else ("filter", 1.0)
                out.append((doc, mt, sc))
                if len(out) >= limit:
                    break
        self.queries.append(native)
        return out, native, []

    def follow(self, edge: Edge, table: str, row: Dict[str, Any], cap: int):
        if edge.child == table:              # follow the reference to the target document
            value = nosql_store.get_path(row, edge.child_fields[0])
            i = self.by_id[edge.parent].get(value)
            self.queries.append(f"db.{edge.parent}.find({{'_id': {json.dumps(value)}}})")
            return edge.parent, ([self.docs[edge.parent][i]] if i is not None else []), (1 if i is not None else 0)
        # documents in the child collection that reference this one
        rid = row.get("_id")
        hits = [d for d, f in zip(self.docs[edge.child], self.flat[edge.child]) if f.get(edge.child_fields[0]) == rid]
        self.queries.append(f"db.{edge.child}.find({{'{edge.child_fields[0]}': {json.dumps(rid)}}})")
        return edge.child, hits[:cap], len(hits)

    def schema(self) -> Dict[str, Any]:
        return {"paradigm": "document (JSON collections)",
                "note": "Links are document references declared in db1_collections.json, not SQL foreign keys.",
                "collections": {c: {"documents": len(d), "primary_key": "_id", "fields": self.field_sets[c]}
                                for c, d in self.docs.items()},
                "relationships": [{"kind": e.kind, "child": e.child, "child_columns": list(e.child_fields),
                                   "parent": e.parent, "parent_columns": list(e.parent_fields), "label": e.label}
                                  for e in self.edges]}


# -- validation ----------------------------------------------------------------------

def validate(engine, spec: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        raise SubqueryError("subquery must be a JSON object")
    target = spec.get("target")
    if target not in engine.tables:
        raise SubqueryError(f"{engine.db_id} has no table or collection {target!r}")
    allowed = set(engine.fields(target))
    where = spec.get("where") or []
    if not isinstance(where, list):
        raise SubqueryError("where must be a list")
    for cond in where:
        if not isinstance(cond, dict) or cond.get("field") not in allowed:
            raise SubqueryError(f"{target} has no field {cond.get('field') if isinstance(cond, dict) else cond!r}")
        if cond.get("op") not in OPS:
            raise SubqueryError(f"unsupported operator {cond.get('op')!r}; use one of {sorted(OPS)}")
    combine = spec.get("combine", "all")
    if combine not in ("all", "any"):
        raise SubqueryError("combine must be 'all' or 'any'")
    limit = max(1, min(int(spec.get("limit") or 25), 200))
    expand = spec.get("expand") or {}
    return {"id": spec.get("id") or "subquery", "target": target, "where": where, "combine": combine,
            "limit": limit, "expand": {"max_hops": max(0, min(int(expand.get("max_hops", 0)), 3)),
                                       "row_budget": max(1, min(int(expand.get("row_budget", 120)), 400)),
                                       "per_edge_cap": max(1, min(int(expand.get("per_edge_cap", 12)), 50)),
                                       "terms": [str(t).lower() for t in (expand.get("terms") or [])][:20]}}


# -- discovery ---------------------------------------------------------------------------

@dataclass
class Found:
    table: str
    row: Dict[str, Any]
    hop: int
    score: float
    path: List[str] = field(default_factory=list)
    match: Optional[str] = None


def _term_hits(row: Dict[str, Any], terms: List[str]) -> int:
    if not terms:
        return 0
    text = " ".join(str(v).lower() for v in _flatten(row).values() if v is not None)
    return sum(1 for t in terms if t in text)


def discover(engine, seeds: List[Found], max_hops: int, row_budget: int, per_edge_cap: int,
             terms: List[str]) -> Dict[Tuple, Found]:
    found: Dict[Tuple, Found] = {(s.table,) + engine.pk(s.table, s.row): s for s in seeds}
    frontier = list(seeds)
    for hop in range(1, max_hops + 1):
        nxt = []
        for cur in frontier:
            for edge in engine.edges:
                if cur.table not in (edge.child, edge.parent):
                    continue
                other, rows, fanout = engine.follow(edge, cur.table, cur.row, per_edge_cap)
                w = edge.weight / (1.0 + math.log2(max(1, fanout)))
                for r in rows:
                    s = cur.score * HOP_DECAY * w * (1.25 if _term_hits(r, terms) else 1.0)
                    s = min(s, 1.0)
                    if s < MIN_SCORE:
                        continue
                    key = (other,) + engine.pk(other, r)
                    if key in found and found[key].score >= s:
                        continue
                    found[key] = Found(other, r, hop, round(s, 4), cur.path + [edge.label])
                    nxt.append(found[key])
                    if len(found) >= row_budget:
                        return found
        frontier = nxt
    return found


def bridge_keys(db_id: str, items: Iterable[Found]) -> Dict[str, Dict[str, List[str]]]:
    """concept -> value -> where it was found ('table.field'), for the identifiers other databases share."""
    spec = _mapping().get("bridge_keys", {}).get(db_id, {})
    out: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for f in items:
        flat = _flatten(f.row)
        for fld, concept in spec.get(f.table, {}).items():
            v = flat.get(fld)
            if v in (None, ""):
                continue
            v = canonical_code(str(v)) if concept == "item_code" else str(v).strip()
            out[concept][v].add(f"{f.table}.{fld}")
    return {c: {v: sorted(w) for v, w in vals.items()} for c, vals in out.items()}


# -- the engine a node serves ------------------------------------------------------

class NodeEngine:
    """Everything one database service can do, against its own data only."""

    def __init__(self, db_id: str):
        self.db_id = db_id
        self._lock = threading.Lock()
        self._engine = None
        self._version = None

    def data_files(self) -> List[str]:
        if self.db_id == "db1":
            store = os.path.dirname(paths.nosql_file())
            return [paths.db_path("db1")] + [os.path.join(store, f) for f in
                                             [nosql_store.SCAN_FILE] + [v[0] for v in nosql_store.COLLECTIONS.values()]]
        return [paths.db_path(self.db_id)]

    def data_version(self) -> int:
        v = 0
        for p in self.data_files():
            try:
                v = max(v, os.stat(p).st_mtime_ns)
            except OSError:
                pass
        return v

    def engine(self):
        with self._lock:
            version = self.data_version()
            if self._engine is None or version != self._version:
                self._engine = (DocEngine(os.path.dirname(paths.nosql_file())) if self.db_id == "db1"
                                else SqlEngine(self.db_id, paths.db_path(self.db_id)))
                self._version = version
            eng = self._engine
            eng.queries = []
            return eng

    def schema(self) -> Dict[str, Any]:
        out = self.engine().schema()
        if self.db_id == "db1":   # the authoritative relational tables behind the documents
            out["authoritative_sqlite"] = SqlEngine("db1", paths.db_path("db1")).schema()
        out["bridge_keys"] = _mapping().get("bridge_keys", {}).get(self.db_id, {})
        return out

    def run(self, spec: Dict[str, Any], discover_context: bool = True) -> Dict[str, Any]:
        import time
        t0 = time.perf_counter()
        eng = self.engine()
        q = validate(eng, spec)
        hits, native, params = eng.select(q["target"], q["where"], q["combine"], q["limit"])
        t1 = time.perf_counter()
        seeds = [Found(q["target"], r, 0, sc, [], mt) for r, mt, sc in hits]
        ex = q["expand"]
        found = discover(eng, seeds, ex["max_hops"], ex["row_budget"], ex["per_edge_cap"], ex["terms"]) \
            if (discover_context and ex["max_hops"] > 0 and seeds) else {(s.table,) + eng.pk(s.table, s.row): s for s in seeds}
        t2 = time.perf_counter()
        context = sorted((f for f in found.values() if f.hop > 0), key=lambda f: -f.score)
        return {
            "subquery_id": q["id"], "database": self.db_id, "paradigm": eng.paradigm,
            "native_query": native, "params": [p for p in params][:-1] if eng.paradigm == "relational" else [],
            "matches": [{"table": f.table, "pk": eng.pk_dict(f.table, f.row), "match": f.match,
                         "score": f.score, "row": f.row} for f in seeds],
            "context": [{"table": f.table, "pk": eng.pk_dict(f.table, f.row), "hop": f.hop, "score": f.score,
                         "path": f.path, "row": f.row} for f in context],
            "context_summary": dict(Counter(f.table for f in context)),
            "bridge_keys": bridge_keys(self.db_id, found.values()),
            "local_queries_executed": len(eng.queries),
            "local_query_sample": eng.queries[:8],
            "timing_ms": {"subquery": round((t1 - t0) * 1000, 2), "discovery": round((t2 - t1) * 1000, 2)},
        }

    # -- the Phase 1 wrapper contract, answered locally (used by remote wrappers) --

    def legacy_lookup(self, key: str) -> Dict[str, Any]:
        if self.db_id == "db1":
            from integration.wrappers.nosql_wrapper import NoSqlDocumentWrapper
            return NoSqlDocumentWrapper(paths.nosql_file()).query(key)
        if self.db_id in ("db2", "db3"):
            from integration.wrappers.sql_wrapper import SqliteRelationalWrapper
            sid, name, nk = {"db2": ("db2_distributor", "Distributor Logistics ERP", "batch_serial"),
                             "db3": ("db3_manufacturer", "CDSCO Manufacturer Master Registry", "product_uid")}[self.db_id]
            return SqliteRelationalWrapper(sid, os.path.basename(paths.db_path(self.db_id)), name, nk).query(key)
        from api.ministry_service import MinistryDataStore
        store = MinistryDataStore(paths.db_path("db4"))
        complaints, blacklist = store.get_complaints(key), store.get_blacklist(key)
        labs, alerts = store.get_lab_reports(key), store.get_alerts(key)
        return {"source_id": "db4_ministry", "native_query": f"SELECT * FROM complaints WHERE complaint_item_ref = '{key}' (+ blacklist, lab_reports, public_alerts)",
                "paradigm": "HTTP REST Microservice (federated node)", "protocol": "HTTP/1.1 REST",
                "found": bool(complaints or blacklist or labs or alerts), "complaints": complaints,
                "blacklist_entry": blacklist[0] if blacklist else None, "lab_reports": labs, "alerts": alerts,
                "count": len(complaints), "used_live_http": True}

    def legacy_catalog(self) -> List[Dict[str, Any]]:
        """The rows integration/entity_resolver.py reads from DB3 / DB2."""
        with closing(sqlite3.connect(f"file:{paths.db_path(self.db_id)}?mode=ro", uri=True)) as c:
            c.row_factory = sqlite3.Row
            if self.db_id == "db3":
                return [dict(r) for r in c.execute(
                    "SELECT p.product_uid, p.product_name, p.generic_name, p.batch_number, p.manufacturer_id, "
                    "m.company_name AS mfg_name FROM products p LEFT JOIN manufacturers m "
                    "ON p.manufacturer_id = m.manufacturer_id")]
            if self.db_id == "db2":
                return [dict(r) for r in c.execute("SELECT batch_id, batch_serial FROM distribution_batches")]
        return []
