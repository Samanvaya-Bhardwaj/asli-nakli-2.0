import pytest
from asali_node.verify.banned_words import problems_in
from asali_node.verify.cities import distance_km
from asali_node.verify.models import Reason
from asali_node.verify.rules import reasons
from asali_node.verify.verdict import verdict_of
from asali_node.verify.wording import describe
from builders import alert, edit, ev, facts, normal_chain


def test_delhi_to_mumbai_is_about_1150_km():
    assert 1100 < distance_km("Delhi", "Mumbai") < 1200


@pytest.mark.parametrize(
    "strengths, expect",
    [
        ([], "genuine"),
        (["caution"], "caution"),
        (["cannot_check"], "cannot_check"),
        (["caution", "cannot_check"], "cannot_check"),
        (["do_not_use", "cannot_check"], "do_not_use"),  # missing sources do not block a do-not-use
        (["caution", "do_not_use"], "do_not_use"),
    ],
)
def test_precedence(strengths, expect):
    assert verdict_of([Reason("X", s, "t") for s in strengths]) == expect  # type: ignore[arg-type]


def result(f):
    rs = reasons(f)
    v = verdict_of(rs)
    return v, rs, describe(v, rs, f)


def test_genuine_sold_sentence():
    _, _, d = result(facts())
    assert d["headline"] == "Genuine. Made by Kesar Biologics, sold by Sharma Medicos, Delhi on 12 Nov 2026."


def test_genuine_in_stock_sentence():
    shop = normal_chain()[2]
    f = facts(chain=(*normal_chain()[:2], edit(shop, [shop.view.events[0]])))
    assert (
        "has not recorded a sale yet" in result(f)[2]["headline"]
        or "received it on 5 Nov 2026" in result(f)[2]["headline"]
    )


def test_copied_code_sentence_names_both_shops():
    f = facts(other_receives=(ev("shop-mumbai", "receive", 6, from_org="dist-south", ref="X"),),
              other_sells=(ev("shop-mumbai", "sell", 14, ref="B9"),))  # fmt: skip
    v, _, d = result(f)
    assert v == "do_not_use"
    assert "Sharma Medicos, Delhi" in d["headline"] and "Apna Chemist, Mumbai" in d["headline"]
    assert d["action"].startswith("Do not take this medicine")


def test_cannot_check_names_who_did_not_answer_and_says_retry():
    v, _, d = result(facts(missing=("regulator",)))
    assert (
        v == "cannot_check" and "Drug Control did not answer" in d["headline"] and "Try again" in d["action"]
    )


@pytest.mark.parametrize("f", [facts(), facts(batch_status="recalled"), facts(missing=("regulator",)),
                               facts(alerts=(alert("nsq"),)), facts(issuer_known=False, chain=())])  # fmt: skip
def test_no_headline_or_reason_uses_a_banned_word_a_dash_or_an_exclamation_mark(f):
    _, rs, d = result(f)
    for text in [d["headline"], d["action"], *[r.text for r in rs]]:
        assert problems_in(text) == [], text
