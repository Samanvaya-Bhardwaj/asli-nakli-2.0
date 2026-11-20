"""The asking node: it asks every organisation on the route for context, merges it, and searches the text with it."""

import asyncio

from asali_node.network.client import SourceUnavailable
from asali_node.verify.context import context_documents, gather_context
from asali_node.verify.trace import Trace
from builders import LOT, G, S, facts

ORGS = [
    {"org_id": "kesar", "org_type": "pharma"}, {"org_id": "dist-south", "org_type": "distributor"},
    {"org_id": "shop-delhi", "org_type": "shop"}, {"org_id": "regulator", "org_type": "regulator"},
    {"org_id": "consumer-delhi", "org_type": "consumer"},
]  # fmt: skip


def term(key, text, score, org_table="batches", step=1, qm=False):
    return {"term": text, "key": key, "kind": "text", "score": score, "query_match": qm,
            "source": {"table": org_table, "column": "reason"}, "relationship_path": ["units(lot) -> batches(lot)"], "step": step}  # fmt: skip


class Share:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    async def get(self, org, path, params=None):
        self.asked.append((org, path, params))
        a = self.answers.get((org, path), SourceUnavailable(org, "unreachable"))
        if isinstance(a, Exception):
            raise a
        return a


def ctx(*terms, tables=("units", "batches"), org="x"):
    return {"ranked_context": list(terms), "explored_tables": list(tables), "joins_performed": [{"fk": "units(lot) -> batches(lot)"}],
            "stop_reason": "reached MAX_AUGMENTATION", "org_id": org, "engine": "sqlite"}  # fmt: skip


def run(coro):
    return asyncio.run(coro)


def test_every_organisation_on_the_route_and_the_regulator_and_consumers_are_asked_with_the_pack_and_question_words():
    share = Share({("kesar", "/share/v1/context"): ctx(term("word:dissolution", "dissolution", 1.0))})
    run(gather_context(share, ORGS, Trace(facts())))
    asked = {o for o, _p, _q in share.asked}
    assert asked == {"kesar", "dist-south", "shop-delhi", "regulator", "consumer-delhi"}
    params = share.asked[0][2]
    assert (params["gtin"], params["serial"], params["lot"]) == (G, S, LOT)
    kw = params["kw"].split(",")
    assert "recall" in kw and "insulin glargine" in kw and "Glargikes" in kw


def test_contexts_are_merged_and_an_organisation_that_did_not_answer_is_listed_not_hidden():
    share = Share({
        ("kesar", "/share/v1/context"): ctx(term("word:dissolution", "dissolution", 1.0), org="kesar"),
        ("shop-delhi", "/share/v1/context"): ctx(term("word:dissolution", "dissolution", 2.0), term("word:humid", "humid", 1.0), org="shop-delhi"),
    })  # fmt: skip
    out = run(gather_context(share, ORGS, Trace(facts())))
    assert out["terms"][0]["term"] == "dissolution"
    assert out["terms"][0]["organisations"] == ["kesar", "shop-delhi"]
    by = {o["org_id"]: o for o in out["organisations"]}
    assert by["kesar"]["status"] == "answered" and by["dist-south"]["status"] == "unreachable"
    assert by["kesar"]["explored_tables"] == ["units", "batches"]


def test_the_lot_and_the_serial_are_anchors_not_context():
    share = Share(
        {
            ("kesar", "/share/v1/context"): ctx(
                term(f"id:{LOT.upper()}", LOT, 5.0), term("word:humid", "humid", 1.0)
            )
        }
    )
    out = run(gather_context(share, ORGS, Trace(facts())))
    assert [t["term"] for t in out["terms"]] == ["humid"]
    assert out["anchors"][0]["term"] == LOT


def context_block(*pairs):
    return {
        "terms": [
            {"term": t, "key": f"word:{t}", "kind": "text", "score": s, "organisations": ["kesar"]}
            for t, s in pairs
        ]
    }


def doc(doc_id, body, kind="operational", created=1_790_000_000):
    return {"id": doc_id, "doc_type": "deviation_report", "kind": kind, "title": "t", "body": body, "created_at": created,
            "links": [], "issue_labels": [], "org_id": "kesar", "meta": {}}  # fmt: skip


def test_documents_are_found_by_context_terms_and_ranked_by_how_many_matter():
    block = context_block(("dissolution", 1.0), ("humid", 0.6), ("tablet", 0.2))
    share = Share({("kesar", "/share/v1/documents/search"): {"hits": [
        doc("d1", "Dissolution failed and the store was humid"),
        doc("d2", "Dissolution was fine"),
        doc("d3", "A note about parking"),
    ]}})  # fmt: skip
    hits = run(context_documents(share, ORGS, Trace(facts()), block, linked_ids=set()))
    assert [h["doc_id"].split(":")[-1] for h in hits] == [
        "d1"
    ]  # d2 has one match only: not enough to be "highly related"
    assert hits[0]["matched_terms"] == ["dissolution", "humid"]
    assert hits[0]["found_by"] == "context"


def test_documents_already_linked_to_the_pack_are_not_shown_again():
    block = context_block(("dissolution", 1.0), ("humid", 0.6))
    share = Share(
        {("kesar", "/share/v1/documents/search"): {"hits": [doc("d1", "Dissolution failed, humid store")]}}
    )
    assert run(context_documents(share, ORGS, Trace(facts()), block, linked_ids={"kesar:d1"})) == []


def test_the_search_asks_by_words_not_by_link_keys():
    block = context_block(("dissolution", 1.0), ("humid", 0.6))
    share = Share({("kesar", "/share/v1/documents/search"): {"hits": []}})
    run(context_documents(share, ORGS, Trace(facts()), block, linked_ids=set()))
    params = next(p for o, path, p in share.asked if path == "/share/v1/documents/search")
    assert "dissolution" in params["q"] and "link_keys" not in params


def test_no_context_means_no_search():
    share = Share({})
    assert run(context_documents(share, ORGS, Trace(facts()), context_block(), linked_ids=set())) == []
    assert share.asked == []
