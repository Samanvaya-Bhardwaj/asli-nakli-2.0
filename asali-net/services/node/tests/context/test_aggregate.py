from asali_node.context.aggregate import aggregate


def term(key, text, score, table="t", column="c", step=0, qm=False, path=None):
    return {"term": text, "key": key, "kind": "text", "score": score, "query_match": qm,
            "source": {"table": table, "column": column}, "relationship_path": path or ["(query result)"], "step": step}  # fmt: skip


def local(*terms):
    return {"ranked_context": list(terms), "explored_tables": ["t"], "stop_reason": "x"}


def test_a_term_found_by_two_organisations_outranks_the_same_score_found_by_one():
    out = aggregate({
        "tarang": local(term("word:dissolution", "dissolution", 1.0), term("word:alpha", "alpha", 1.0)),
        "dist-north": local(term("word:dissolution", "dissolution", 1.0)),
    })  # fmt: skip
    assert out["terms"][0]["key"] == "word:dissolution"
    assert out["terms"][0]["organisations"] == ["dist-north", "tarang"]
    assert "found independently by 2 organisations" in " ".join(out["terms"][0]["why_relevant"])


def test_scores_are_normalised_per_organisation_so_one_cannot_drown_the_others():
    out = aggregate({
        "loud": local(term("word:a", "a", 50.0), term("word:b", "b", 40.0)),
        "quiet": local(term("word:c", "c", 0.5)),
    })  # fmt: skip
    by = {t["key"]: t["score"] for t in out["terms"]}
    assert by["word:c"] == by["word:a"]  # both are the best term of their own organisation


def test_a_term_that_matches_the_question_is_boosted():
    out = aggregate({"a": local(term("word:x", "x", 1.0, qm=True), term("word:y", "y", 1.0))})
    assert out["terms"][0]["key"] == "word:x"


def test_the_identifiers_the_question_asked_about_are_reported_apart():
    out = aggregate(
        {"a": local(term("id:MV-2606-004", "MV-2606-004", 1.0), term("word:z", "z", 0.5))},
        anchors=["MV-2606-004"],
    )
    assert [t["key"] for t in out["terms"]] == ["word:z"]
    assert out["anchors"][0]["term"] == "MV-2606-004"


def test_every_term_keeps_where_it_came_from():
    out = aggregate(
        {
            "tarang": local(
                term(
                    "word:q",
                    "q",
                    1.0,
                    table="recalls",
                    column="reason",
                    step=2,
                    path=["units(lot) -> batches(lot)", "recalls(lot) -> batches(lot)"],
                )
            )
        }
    )
    prov = out["terms"][0]["provenance"][0]
    assert (prov["organisation"], prov["table"], prov["column"], prov["step"]) == (
        "tarang",
        "recalls",
        "reason",
        2,
    )
    assert "reached through 2 foreign key join" in " ".join(out["terms"][0]["why_relevant"])


def test_an_organisation_that_found_nothing_is_listed_as_such_not_as_a_contributor():
    out = aggregate(
        {
            "a": local(term("word:x", "x", 1.0)),
            "b": {"ranked_context": [], "explored_tables": ["t"], "stop_reason": "no rows"},
        }
    )
    assert out["organisations_contributing"] == ["a"]
    assert out["organisations_asked"] == ["a", "b"]


def test_a_category_term_whose_value_is_the_pack_itself_is_an_anchor_too():
    out = aggregate({"a": local(term("categorical:gtin=08901002000048", "gtin=08901002000048", 3.0), term("word:z", "z", 0.5))},
                    anchors=["08901002000048"])  # fmt: skip
    assert [t["term"] for t in out["terms"]] == ["z"]
    assert out["anchors"][0]["term"] == "gtin=08901002000048"
