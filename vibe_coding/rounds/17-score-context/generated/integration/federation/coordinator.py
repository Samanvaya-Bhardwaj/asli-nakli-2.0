"""
coordinator.py
--------------
Phase 3 federated query coordinator, built on the Phase 1 GAV mediator.

    question --parse--> concepts + intents + terms
             --route--> the databases that can answer, each with the reason
             --unfold-> one subquery per (database, GAV view of a concept),
                        written in that database's own table and field names
                        (integration/schema_mapping.json, section "phase3")
             --send---> every database in parallel, over HTTP, with its own token;
                        each one executes its subqueries and discovers its own
                        context through its own FK-PK relationships
             --collect> per-database results with provenance (database, machine,
                        native query, FK path of every context row), and the
                        status of every database: ok / timeout / unreachable / ...
             --combine> grouped on the business identifiers the databases share
             --verify-> for medicine codes, the existing Phase 1 verdict, computed
                        by the unchanged GAV resolver / GlobalItemHistory / veto /
                        trust engines through remote wrappers - only when all four
                        databases answered (a missing source is not evidence)

The coordinator keeps no copy of any database: everything it returns is built from
the answers to this one query, in memory.
"""

from __future__ import annotations
import ipaddress
import json
import os
import socket
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from integration.federation import runtime
from integration.federation.query_parser import ParsedQuery, parse
from integration.federation.remote import NodeError, client, collect_status

MAPPING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema_mapping.json")
MAX_SUBQUERIES_PER_DB = 12
MAX_VERDICTS = 3


def _gav() -> Dict[str, Any]:
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["phase3"]


# -- planning ---------------------------------------------------------------------------

def route(pq: ParsedQuery) -> Dict[str, Any]:
    gav = _gav()
    reasons: Dict[str, List[str]] = {d: [] for d in runtime.DB_IDS}
    concepts = pq.concepts()
    intents = pq.intents
    if "authenticity" in intents or (concepts.get("item_code") and not intents):
        chosen = set(runtime.DB_IDS)
        for d in chosen:
            reasons[d].append("a verdict on a medicine code needs all four sources"
                              if "authenticity" in intents else "holds the medicine code under its own column name")
    elif intents:
        chosen = set()
        for i in intents:
            for d in gav["intents"][i]["databases"]:
                chosen.add(d)
                reasons[d].append(f"{i}: {gav['intents'][i]['why']}")
    else:
        chosen = set()
    for concept, values in concepts.items():
        dbs = gav["concept_databases"].get(concept, [])
        if concept == "item_code" and chosen:
            continue                      # the code is looked up inside the chosen databases
        if chosen and set(dbs) & chosen:
            continue
        for d in dbs:
            chosen.add(d)
            reasons[d].append(f"holds {concept.replace('_', ' ')} {', '.join(values)}")
    if not chosen:                         # only free text: every source matches it locally
        chosen = set(runtime.DB_IDS)
        for d in chosen:
            reasons[d].append("free-text question: matched against this database's own name and text columns")
    return {"databases": sorted(chosen),
            "reasons": {d: reasons[d] for d in sorted(chosen)},
            "not_queried": {d: "not relevant to " + (", ".join(intents) or "the identifiers given")
                            for d in runtime.DB_IDS if d not in chosen}}


def score_params(max_augmentation: Optional[int] = None, top_n: Optional[int] = None) -> Dict[str, int]:
    """SCORE limits: request value, else ASALI_SCORE_MAX_AUGMENTATION / ASALI_SCORE_TOP_N, else 4 / 20."""
    return {"max_augmentation": int(max_augmentation if max_augmentation is not None
                                    else os.environ.get("ASALI_SCORE_MAX_AUGMENTATION") or 4),
            "top_n": int(top_n if top_n is not None else os.environ.get("ASALI_SCORE_TOP_N") or 20)}


def context_keywords(pq: ParsedQuery) -> List[str]:
    """The question's own words and intent phrases, plus each detected intent's vocabulary
    ('cold chain' brings 'temperature', 'excursion', ...): disclosed query expansion that
    each database applies to its own tables and columns."""
    from integration.federation.query_parser import INTENT_WORDS
    words = list(pq.keywords)
    for i in pq.intents:
        if i != "authenticity":
            words.extend(w.strip() for w in INTENT_WORDS[i] if w.strip() not in words)
    return words


def unfold(pq: ParsedQuery, databases: List[str], qid: str, max_hops: int = 2,
           row_budget: int = 120, method: str = "score", max_augmentation: Optional[int] = None,
           top_n: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
    """GAV unfolding: each global concept becomes subqueries over each source's own views."""
    concepts = _gav()["concepts"]
    present = pq.concepts()
    expand = {"max_hops": max_hops, "row_budget": row_budget, "terms": pq.terms, "method": method,
              "keywords": context_keywords(pq), **score_params(max_augmentation, top_n)}
    plan: Dict[str, List[Dict[str, Any]]] = {}
    for d in databases:
        subs = []
        # a table that holds two of the identifiers asked about gets one subquery
        # requiring both ('shipments from DIST-004 to VND-012'), not two that each match half
        by_target: Dict[str, List[tuple]] = {}
        for concept, values in present.items():
            for view in concepts.get(concept, {}).get(d, []):
                by_target.setdefault(view["target"], []).append((concept, view, values))
        for target, views in by_target.items():
            if len({c for c, _v, _vals in views}) > 1 and all(len(vals) == 1 for _c, _v, vals in views):
                subs.append({"concept": "+".join(sorted({c for c, _v, _vals in views})), "target": target,
                             "where": [{"field": v["field"], "op": v["op"], "value": vals[0]} for _c, v, vals in views]})
                continue
            for concept, view, values in views:
                for v in values:
                    subs.append({"concept": concept, "target": target,
                                 "where": [{"field": view["field"], "op": view["op"], "value": v}]})
        if not present and pq.terms:
            for view in concepts["text"].get(d, []):
                subs.append({"concept": "text", "target": view["target"],
                             "where": [{"field": view["field"], "op": "contains_any", "value": pq.terms}]})
        for n, s in enumerate(subs[:MAX_SUBQUERIES_PER_DB], start=1):
            s.update({"id": f"{qid}.{d}.{n}", "combine": "all", "limit": 25, "expand": expand})
        plan[d] = subs[:MAX_SUBQUERIES_PER_DB]
    return plan


# -- execution ------------------------------------------------------------------------------

def _run_on(db_id: str, subqueries: List[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = runtime.node_config(db_id)
    out = {"database": db_id, "name": runtime.DB_NAMES[db_id], "url": cfg.url, "machine": cfg.machine,
           "status": "ok", "served_by": None, "subqueries": [], "errors": []}
    t0 = time.perf_counter()
    c = client(db_id)
    for sq in subqueries:
        try:
            res = c.request("POST", "/api/v3/subquery", {"subquery": sq})
            out["served_by"] = out["served_by"] or res.get("source")
            r = res["result"]
            r["round_trip_ms"] = res.get("_elapsed_ms")
            r["concept"] = sq.get("concept")
            r["sent"] = sq
            out["subqueries"].append(r)
        except NodeError as e:
            out["errors"].append({"subquery_id": sq["id"], "status": e.status, "message": e.message})
            if e.status in ("timeout", "unreachable", "auth_failed"):
                out["status"] = e.status
                break                     # the database is gone; do not wait on every subquery
            out["status"] = "partial"
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return out


def _gather(per_db: Dict[str, Dict[str, Any]], key: str) -> Dict[str, Dict[str, Dict[str, set]]]:
    by_concept: Dict[str, Dict[str, Dict[str, set]]] = {}
    for d, res in per_db.items():
        for sq in res["subqueries"]:
            for concept, values in sq.get(key, {}).items():
                for v, where in values.items():
                    by_concept.setdefault(concept, {}).setdefault(v, {}).setdefault(d, set()).update(where)
    return by_concept


def _combine(per_db: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Grouped on shared business identifiers. 'medicines' are the codes the
    subqueries themselves matched; 'related_in_context' are codes that only turned
    up in some database's discovered context (other batches of the same
    distributor, say) - kept apart because they answer a different question.
    Ranking that context by relevance is Requirement 3.
    """
    matched = _gather(per_db, "match_bridge_keys")
    by_concept = _gather(per_db, "bridge_keys")
    items = [{"item_code": code, "matched_in": sorted(dbs),
              "also_in_context_of": sorted(set(by_concept.get("item_code", {}).get(code, {})) - set(dbs))}
             for code, dbs in matched.get("item_code", {}).items()]
    items.sort(key=lambda x: (-len(x["matched_in"]), x["item_code"]))
    related = [{"item_code": code, "in_context_of": sorted(dbs)}
               for code, dbs in by_concept.get("item_code", {}).items() if code not in matched.get("item_code", {})]
    related.sort(key=lambda x: (-len(x["in_context_of"]), x["item_code"]))
    near = [{"database": d, "subquery_id": sq["subquery_id"], **nm}
            for d, res in per_db.items() for sq in res["subqueries"] for nm in sq.get("near_misses", [])]
    links = []
    for concept, values in by_concept.items():
        if concept == "item_code":
            continue
        for v, dbs in values.items():
            if len(dbs) >= 2:
                links.append({"concept": concept, "value": v, "databases": sorted(dbs),
                              "where": {d: sorted(w) for d, w in dbs.items()}})
    links.sort(key=lambda x: (-len(x["databases"]), x["concept"], x["value"]))
    return {"medicines": items, "cross_source_links": links, "related_in_context": related,
            "near_misses": near}


# Match types that may stand in for the code the user typed. 'one_edit' may not:
# a counterfeit printed one character away from a real code would otherwise be
# verified as the real product and inherit its clean verdict (RUNNING.md 5.2).
SAFE_MATCHES = ("exact", "tidied", "lookalike")


def _seed_codes(per_db: Dict[str, Dict[str, Any]], pq: ParsedQuery) -> List[str]:
    """Codes to verify: each typed code, or the registered code it unambiguously denotes."""
    from integration.uncertainty.standardize import canonical_code
    codes: List[str] = []
    for typed in pq.item_codes:
        stand_in = []
        for d in ("db3", "db2", "db1", "db4"):          # DB3 first: it is the register
            for sq in per_db.get(d, {}).get("subqueries", []):
                cond = sq["sent"]["where"][0]
                if sq.get("concept") != "item_code" or cond.get("value") != typed or "." in cond["field"]:
                    continue
                for m in sq["matches"]:
                    v = m["row"].get(cond["field"])
                    if v and m.get("match") in SAFE_MATCHES and canonical_code(str(v)) not in stand_in:
                        stand_in.append(canonical_code(str(v)))
            if stand_in:
                break
        # exactly one registered stand-in: check that; otherwise check what was typed
        # (an unknown code then meets the phantom-serial veto, as in Phase 1)
        pick = stand_in[0] if len(stand_in) == 1 else typed
        if pick not in codes:
            codes.append(pick)
    return codes


def _verdict(code: str, statuses: Dict[str, str]) -> Dict[str, Any]:
    from integration import resolver
    if resolver.FEDERATION_MODE != "remote":
        return {"item_code": code, "status": "NOT_RUN",
                "reason": "the GAV resolver in this process reads local files (ASALI_FEDERATION is not 'remote')"}
    down = {d: s for d, s in statuses.items() if s != "ok"}
    if down:
        return {"item_code": code, "status": "WITHHELD", "unavailable": down,
                "reason": ("not all four databases answered; the Phase 1 vetoes would read a missing source as "
                           "missing evidence (an unreachable registry looks like a phantom serial)")}
    from api.verify_item import verify
    with collect_status() as during:
        r = verify(code, silent=True)
    down = {d: s for d, s in during.items() if s != "ok"}
    if down:
        return {"item_code": code, "status": "WITHHELD", "unavailable": down,
                "reason": "a database stopped answering while the verdict was being computed"}
    return {"item_code": code, "status": "COMPUTED", "verdict": r["verdict"], "trust_score": r["trust_score"],
            "veto_codes": r["veto_codes"], "lifecycle_state": r["lifecycle_state"], "db_coverage": r["db_coverage"],
            "contradictions": r["contradictions"], "resolved_code": r["resolved_code"],
            "resolution": r["resolution"], "auto_report_due": r.get("auto_report_due"),
            "audit_entry": r.get("audit_entry"),
            "computed_by": "Phase 1 pipeline (GAV resolver -> GlobalItemHistory -> hard vetoes -> trust engine) "
                           "over remote wrappers"}


def federated_query(text: str, max_hops: int = 2, verify: bool = True, method: str = "score",
                    max_augmentation: Optional[int] = None, top_n: Optional[int] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    qid = "Q" + uuid.uuid4().hex[:6]
    pq = parse(text)
    routing = route(pq)
    plan = unfold(pq, routing["databases"], qid, max_hops=max_hops, method=method,
                  max_augmentation=max_augmentation, top_n=top_n)
    with ThreadPoolExecutor(max_workers=len(plan) or 1) as pool:
        futures = {d: pool.submit(_run_on, d, subs) for d, subs in plan.items()}
        per_db = {d: f.result() for d, f in futures.items()}
    t1 = time.perf_counter()

    statuses = {d: per_db[d]["status"] if d in per_db else "not_queried" for d in runtime.DB_IDS}
    combined = _combine(per_db)
    from integration.federation.context_aggregator import aggregate
    query_context = aggregate(per_db, top_n=max(score_params(max_augmentation, top_n)["top_n"], 25))
    verdicts = []
    if verify and (pq.item_codes or "authenticity" in pq.intents):
        all_status = dict(statuses)
        for d in runtime.DB_IDS:            # sources not routed to must still be up for a verdict
            if all_status[d] == "not_queried":
                try:
                    client(d).health()
                    all_status[d] = "ok"
                except NodeError as e:
                    all_status[d] = e.status
        for code in _seed_codes(per_db, pq)[:MAX_VERDICTS]:
            verdicts.append(_verdict(code, all_status))
    return {
        "query_id": qid, "question": text,
        "understanding": {"item_codes": pq.item_codes, "batch_numbers": pq.batch_numbers,
                          "vendor_ids": pq.vendor_ids, "distributor_ids": pq.distributor_ids,
                          "manufacturer_ids": pq.manufacturer_ids, "intents": pq.intents, "terms": pq.terms,
                          "context_keywords": context_keywords(pq),
                          "explanation": pq.explanation},
        "routing": routing,
        "subqueries": plan,
        "sources": per_db,
        "source_status": statuses,
        "partial": any(s not in ("ok", "not_queried") for s in statuses.values()),
        "combined": combined,
        "query_context": query_context,
        "verdicts": verdicts,
        "timing_ms": {"federated_execution": round((t1 - t0) * 1000, 2),
                      "total": round((time.perf_counter() - t0) * 1000, 2)},
    }


# -- deployment status --------------------------------------------------------------------

def _resolve(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "unresolvable"


def _is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def nodes_status() -> Dict[str, Any]:
    cfgs = runtime.all_nodes(required=False)

    def probe(d):
        cfg = cfgs.get(d)
        if not cfg:
            return d, {"database": d, "status": "not_configured"}
        base = {"database": d, "name": runtime.DB_NAMES[d], "configured_url": cfg.url,
                "configured_machine": cfg.machine, "resolved_ip": _resolve(cfg.host)}
        try:
            h = client(d).health()
            return d, {**base, "status": h.get("status"), "reported": h, "round_trip_ms": h.get("_elapsed_ms")}
        except NodeError as e:
            return d, {**base, "status": e.status, "error": e.message}

    with ThreadPoolExecutor(max_workers=4) as pool:
        nodes = dict(pool.map(probe, runtime.DB_IDS))
    up = [n for n in nodes.values() if n.get("status") == "online"]
    ips = {n["resolved_ip"] for n in nodes.values() if "resolved_ip" in n}
    physical = sorted({n["reported"].get("physical_host") for n in up})
    if up and all(_is_loopback(n["resolved_ip"]) for n in up):
        mode = "LOCAL_SIMULATION"
        meaning = ("Every database service is reached at a loopback address on this machine. This shows process "
                   "and data isolation (separate processes, separate data directories, HTTP between them) - it does "
                   "NOT show execution on different machines.")
    elif len(physical) <= 1:
        mode = "SINGLE_HOST_NETWORKED"
        meaning = ("The services are reached over network addresses, but all report the same physical host "
                   f"({', '.join(physical) or 'unknown'}), e.g. Docker containers on one computer. Not multi-machine.")
    else:
        mode = "MULTI_MACHINE"
        meaning = (f"The services report {len(physical)} different physical hosts ({', '.join(physical)}) at "
                   f"{len(ips)} network address(es). Each service also reports the address it saw this coordinator "
                   f"connect from ('seen_client'), which should be this machine's LAN address.")
    return {"coordinator": {"hostname": socket.gethostname(), "physical_host": os.environ.get("ASALI_PHYSICAL_HOST")
                            or socket.gethostname(), "machine_label": os.environ.get("ASALI_MACHINE_LABEL") or "unlabelled"},
            "deployment": {"mode": mode, "meaning": meaning, "distinct_physical_hosts": physical,
                           "distinct_addresses": sorted(ips)},
            "nodes": nodes}
