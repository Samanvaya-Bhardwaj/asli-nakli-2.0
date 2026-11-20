"""Phase 3 rubric 1: every organisation's database has at least four related tables (or collections), joined by keys.

The records about one thing are spread across tables: a pack is in a units table, its batch is in another, the
product in a third, and the keys that join them are declared in the database, not in the code.
"""

from asali_node.context.explore import INFRA_TABLES
from asali_node.context.graph import MongoGraph, SqlGraph


def graph_of(store):
    if hasattr(store, "CONTEXT_COLLECTIONS"):
        return MongoGraph(store.db, store.CONTEXT_COLLECTIONS, store.CONTEXT_REFS)
    return SqlGraph(store.db, skip_tables=INFRA_TABLES)


def test_at_least_four_domain_tables_with_keys_between_them(env):
    g = graph_of(env.rw())
    assert len(g.tables) >= 4, f"{env.spec.org_id} has only {g.tables}"
    joined = {t for e in g.edges for t in (e.child, e.parent)}
    assert len(g.edges) >= 3, f"{env.spec.org_id}: only {[e.label for e in g.edges]}"
    assert len(joined) >= 4, f"{env.spec.org_id}: keys join only {sorted(joined)}"


def test_every_key_points_at_a_table_that_exists_with_the_named_columns(env):
    g = graph_of(env.rw())
    for e in g.edges:
        assert e.child in g.tables and e.parent in g.tables, e.label
        for t, cols in ((e.child, e.child_fields), (e.parent, e.parent_fields)):
            if not hasattr(
                env.rw(), "CONTEXT_COLLECTIONS"
            ):  # a MongoDB collection has no fixed column list until it holds a document
                assert set(cols) <= set(g.fields(t)), f"{e.label}: {t} has {g.fields(t)}"
