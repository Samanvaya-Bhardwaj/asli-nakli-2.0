"""Find the rows of one database that mention the pack, then discover context from them."""

from typing import Any

from asali_node.context.graph import Graph
from asali_node.context.score import discover

Roots = list[tuple[str, str, str]]  # (table or collection, column or dotted path, "serial" | "gtin" | "lot")

# Tables every node has that say nothing about packs: logins, scan corrections, document links.
INFRA_TABLES = ("staff", "users", "scan_corrections", "scan_fixes", "document_links", "doc_links", "doc_refs",
                "usr_mst", "scn_corr", "doc_lnk", "scanfixes", "doclinks")  # fmt: skip


def explore(
    graph: Graph, roots: Roots, keys: dict[str, str | None], db_id: str, keywords: list[str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:  # fmt: skip
    found: dict[str, list[dict[str, Any]]] = {}
    for table, column, kind in roots:
        value = keys.get(kind)
        if not value:
            continue
        seen = {tuple(sorted(graph.pk_dict(table, r).items())) for r in found.get(table, [])}
        for row in graph.find(table, column, [value]):
            ident = tuple(sorted(graph.pk_dict(table, row).items()))
            if ident not in seen:
                seen.add(ident)
                found.setdefault(table, []).append(row)
    if not found:
        return {"ranked_context": [], "explored_tables": [], "joins_performed": [], "query_result": {"tables": {}},
                "stop_reason": "no row in this database mentions the pack"}  # fmt: skip
    tables = list(found)
    out = discover(graph, db_id, tables[0], found[tables[0]], keywords, params,
                   extra_seeds=[(t, found[t]) for t in tables[1:]])  # fmt: skip
    return out
