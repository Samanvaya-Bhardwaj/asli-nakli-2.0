"""Context discovery on a small SQLite database with known foreign keys and known planted facts."""

import pytest
from asali_node.context.graph import SqlGraph
from asali_node.context.score import discover
from asali_node.stores.sqlbase import SqlDb

SCHEMA = [
    "CREATE TABLE products (gtin TEXT PRIMARY KEY, brand TEXT, storage_note TEXT)",
    "CREATE TABLE batches (lot TEXT PRIMARY KEY, gtin TEXT REFERENCES products(gtin), expiry TEXT)",
    "CREATE TABLE units (serial TEXT PRIMARY KEY, lot TEXT REFERENCES batches(lot))",
    "CREATE TABLE recalls (recall_id TEXT PRIMARY KEY, lot TEXT REFERENCES batches(lot), reason TEXT)",
    "CREATE TABLE staff (username TEXT PRIMARY KEY, password_hash TEXT)",
    "CREATE TABLE weather (day TEXT PRIMARY KEY, note TEXT)",  # no key to anything
]


@pytest.fixture
def db(tmp_path):
    d = SqlDb("sqlite", str(tmp_path / "t.sqlite"), "rw")
    for s in SCHEMA:
        d.run(s)
    d.run("INSERT INTO products VALUES ('G1', 'Metvra', 'Store below 25 C, keep away from moisture')")
    d.run("INSERT INTO products VALUES ('G2', 'Calpex', 'Store in a cool dry place')")
    for lot, gtin in (("L1", "G1"), ("L2", "G1"), ("L3", "G2")):
        d.run("INSERT INTO batches VALUES (?, ?, '2028-01-31')", lot, gtin)
    for i in range(20):
        d.run("INSERT INTO units VALUES (?, ?)", f"S{i:02d}", "L1" if i < 10 else "L2")
    d.run("INSERT INTO recalls VALUES ('R1', 'L1', 'dissolution failed in stability testing')")
    d.run("INSERT INTO staff VALUES ('asha', 'x')")
    d.run("INSERT INTO weather VALUES ('mon', 'rainy and humid')")
    return d


def run(db, serial="S01", **kw):
    g = SqlGraph(db, skip_tables=["staff"])
    seed = g.find("units", "serial", [serial])
    return g, discover(g, "t", "units", seed, kw.pop("keywords", ["recall", "quality"]), **kw)


def test_the_graph_reads_the_foreign_keys_from_the_database(db):
    g = SqlGraph(db, skip_tables=["staff"])
    labels = {e.label for e in g.edges}
    assert labels == {
        "batches(gtin) -> products(gtin)",
        "units(lot) -> batches(lot)",
        "recalls(lot) -> batches(lot)",
    }
    assert "staff" not in g.tables


def test_context_reaches_a_table_two_joins_away_through_real_keys(db):
    _, out = run(db)
    reason_terms = [t for t in out["ranked_context"] if t["source"]["table"] == "recalls"]
    assert reason_terms, out["explored_tables"]
    assert any("dissolution" in t["term"] for t in reason_terms)
    path = reason_terms[0]["relationship_path"]
    assert path[0].startswith("units(lot) -> batches(lot)")
    assert path[-1] == "batches(lot) -> recalls(lot)" or "recalls(lot)" in path[-1]


def test_every_join_follows_a_declared_foreign_key(db):
    g, out = run(db)
    declared = {e.label for e in g.edges}
    for j in out["joins_performed"]:
        assert j["fk"] in declared or _reverse(j["fk"]) in declared


def _reverse(label: str) -> str:
    a, b = label.split(" -> ")
    return f"{b} -> {a}"


def test_a_table_with_no_key_to_the_result_is_never_explored(db):
    _, out = run(db)
    assert "weather" not in out["explored_tables"]
    assert "staff" not in out["explored_tables"]


def test_the_limit_on_joins_is_respected(db):
    _, out = run(db, params={"max_augmentation": 1})
    assert len(out["joins_performed"]) == 1
    assert "recalls" not in out["explored_tables"] or out["explored_tables"].index("recalls") <= 1


def test_context_about_this_pack_does_not_contain_another_batchs_facts(db):
    _, out = run(db, serial="S15")  # a pack of L2, which has no recall
    assert not any("dissolution" in t["term"] for t in out["ranked_context"])


def test_a_neighbouring_table_that_adds_nothing_is_not_followed(db):
    g = SqlGraph(db, skip_tables=["staff"])
    db.run("INSERT INTO units VALUES ('LONE', 'L3')")
    seed = g.find("units", "serial", ["LONE"])
    out = discover(SqlGraph(db, skip_tables=["staff"]), "t", "units", seed, ["recall"])
    assert "recalls" not in out["explored_tables"]  # batch L3 has no recall rows: the join gives no rows


def test_terms_that_match_the_question_rank_above_those_that_do_not(db):
    _, plain = run(db, keywords=["unrelated"])
    _, asked = run(db, keywords=["dissolution"])

    def rank(out):
        return next(i for i, t in enumerate(out["ranked_context"]) if "dissolution" in t["term"])

    assert rank(asked) <= rank(plain)
    assert next(t for t in asked["ranked_context"] if "dissolution" in t["term"])["query_match"] is True


def test_the_same_question_gives_the_same_context(db):
    _, a = run(db)
    _, b = run(db)
    assert [t["key"] for t in a["ranked_context"]] == [t["key"] for t in b["ranked_context"]]


def test_columns_that_could_identify_a_person_or_another_pack_are_never_terms(db):
    db.run("ALTER TABLE units ADD COLUMN device_hash TEXT")
    db.run("UPDATE units SET device_hash = 'abc123def' WHERE serial = 'S01'")
    _, out = run(db)
    text = " ".join(t["term"] for t in out["ranked_context"])
    assert "abc123def" not in text
    assert "S02" not in text  # the serial of another pack in the same batch


def test_roots_in_two_tables_are_both_explored(db):
    from asali_node.context.explore import explore

    out = explore(SqlGraph(db, skip_tables=["staff"]), [("units", "serial", "serial"), ("recalls", "lot", "lot")],
                  {"serial": "S01", "lot": "L1", "gtin": "G1"}, "t", ["recall"])  # fmt: skip
    assert set(out["query_result"]["tables"]) == {"units", "recalls"}


def test_a_pack_no_row_mentions_gives_an_empty_context_that_says_why(db):
    from asali_node.context.explore import explore

    out = explore(SqlGraph(db, skip_tables=["staff"]), [("units", "serial", "serial")],
                  {"serial": "NOPE", "lot": None, "gtin": None}, "t", ["recall"])  # fmt: skip
    assert out["ranked_context"] == []
    assert "no row" in out["stop_reason"]
