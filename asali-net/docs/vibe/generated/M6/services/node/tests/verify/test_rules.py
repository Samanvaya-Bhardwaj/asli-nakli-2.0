from dataclasses import replace
from datetime import date

import pytest
from asali_node.verify.models import DocSignal, Hop
from asali_node.verify.rules import reasons
from builders import (
    CITY, LOT, NAMES, PRODUCT, TODAY, alert, at, edit, ev, facts, hop, licence, normal_chain, scans,
)  # fmt: skip


def codes(f):
    return [r.code for r in reasons(f)]


def doc(kind, conf=0.95, **kw):
    return DocSignal(kind=kind, doc_id=kw.pop("doc_id", "d1"), confidence=conf, org_id="regulator", quote="q", **kw)


def test_a_normal_pack_raises_nothing():
    assert codes(facts()) == []


@pytest.mark.parametrize(
    "f, expect",
    [
        (facts(issuer_known=False, chain=()), ["NOT_ISSUED"]),
        (facts(chain=(hop("kesar", "pharma", [], known=False, status="never_held"),), batch_status=None, expiry=None), ["NOT_ISSUED"]),
        (facts(issuer_reachable=False, chain=(Hop("kesar", "pharma", "Kesar", "Pune", None, "timeout"),)), ["SOURCE_MISSING"]),
    ],
)
def test_not_issued_needs_an_answer_saying_so(f, expect):
    assert codes(f) == expect


def test_destroyed_at_the_issuer():
    first = hop("kesar", "pharma", [ev("kesar", "commission", 1)], status="destroyed")
    assert codes(facts(chain=(first,))) == ["DESTROYED"]


@pytest.mark.parametrize(
    "f, expect",
    [
        (facts(batch_status="recalled"), True),
        (facts(alerts=(alert("recall"),)), True),
        (facts(alerts=(alert("ban", lot=None),)), True),
        (facts(alerts=(alert("recall", lot="OTHER-LOT"),)), False),
        (facts(alerts=(alert("recall", gtin="08901009999999"),)), False),
        (facts(alerts=(alert("nsq"),)), False),
        (facts(doc_signals=(doc("official_recall_notice", 0.95),)), True),
        (facts(doc_signals=(doc("official_recall_notice", 0.7),)), False),
    ],
)
def test_recalled(f, expect):
    assert ("RECALLED" in codes(f)) is expect


@pytest.mark.parametrize(
    "f, failed, possible",
    [
        (facts(alerts=(alert("nsq"),)), True, False),
        (facts(doc_signals=(doc("official_quality_notice", 0.95),)), True, False),
        (facts(doc_signals=(doc("official_quality_notice", 0.9),)), True, False),
        (facts(doc_signals=(doc("official_quality_notice", 0.7),)), False, True),
        (facts(doc_signals=(doc("official_quality_notice", 0.5),)), False, False),
        (facts(), False, False),
    ],
)
def test_quality_notice_strengths(f, failed, possible):
    c = codes(f)
    assert ("QUALITY_FAILED" in c) is failed and ("QUALITY_NOTICE_POSSIBLE" in c) is possible


@pytest.mark.parametrize("expiry, expect", [(date(2026, 11, 20), False), (date(2026, 11, 19), True), (date(2027, 1, 1), False)])
def test_expiry_today_is_not_expired(expiry, expect):
    assert ("EXPIRED" in codes(facts(expiry=expiry))) is expect


def copied_chain(second_org="shop-mumbai", extra=()):
    return (*normal_chain(), *extra), (ev(second_org, "receive", 6, from_org="dist-south", ref="FORGED"), ev(second_org, "sell", 14, ref="B9"))


def test_a_code_sold_by_two_organisations_is_copied():
    _, (r, s) = copied_chain()
    c = codes(facts(other_receives=(r,), other_sells=(s,)))
    assert "COPIED_CODE" in c


def test_one_shop_selling_twice_is_copied_unless_the_pack_came_back_between():
    shop = normal_chain()[2]
    twice = edit(shop, [*shop.view.events, ev("shop-delhi", "sell", 15, ref="B2")])
    assert "COPIED_CODE" in codes(facts(chain=(*normal_chain()[:2], twice)))
    back = edit(shop, [*shop.view.events, ev("shop-delhi", "return", 13, ref="B1"), ev("shop-delhi", "sell", 15, ref="B2")])
    assert "COPIED_CODE" not in codes(facts(chain=(*normal_chain()[:2], back)))


def test_a_lone_sale_at_a_shop_the_chain_never_reached_is_a_chain_break_not_a_copy():
    only_sold_elsewhere = normal_chain()[:2]
    c = codes(facts(chain=only_sold_elsewhere, other_sells=(ev("shop-mumbai", "sell", 14, ref="B9"),)))
    assert c == ["CHAIN_BREAK"]


def test_chain_break_cases():
    shop = normal_chain()[2]
    no_dispatch = hop("dist-south", "distributor", [ev("dist-south", "receive", 3, from_org="kesar", ref="S1"),
                                                    ev("dist-south", "ship", 4, to_org="shop-delhi", ref="D1")])  # fmt: skip
    wrong_ref = edit(shop, [ev("shop-delhi", "receive", 5, from_org="dist-south", ref="X9")])
    assert codes(facts(chain=(*normal_chain()[:1], no_dispatch, wrong_ref))) == ["CHAIN_BREAK"]
    no_receipt = edit(shop, [ev("shop-delhi", "sell", 12, ref="B1")])
    assert codes(facts(chain=(*normal_chain()[:2], no_receipt))) == ["CHAIN_BREAK"]
    forged = ev("shop-mumbai", "receive", 6, from_org="dist-south", ref="FORGED")
    assert codes(facts(other_receives=(forged,))) == ["CHAIN_BREAK"]
    in_transit = normal_chain()[:2]
    assert codes(facts(chain=in_transit)) == []  # shipped but not yet received is not a break


@pytest.mark.parametrize(
    "lic, expect",
    [
        (licence("shop-delhi", "suspended"), True),
        (licence("shop-delhi", "cancelled"), True),
        (licence("shop-delhi", valid_to=date(2026, 11, 1)), True),  # expired before it handled the pack
        (licence("shop-delhi", valid_to=date(2026, 11, 8)), False),  # expired after the shop received it on the 5th
        (licence("shop-delhi"), False),
    ],
)
def test_unlicensed_holder(lic, expect):
    assert ("UNLICENSED_HOLDER" in codes(facts(licences=(lic,)))) is expect


@pytest.mark.parametrize(
    "stats, expect",
    [
        ((scans("Delhi", 13, 13), scans("Mumbai", 14, 14)), True),
        ((scans("Delhi", 13, 13), scans("Gurugram", 14, 14)), False),  # close by
        ((scans("Delhi", 1, 1), scans("Mumbai", 20, 20)), False),  # far apart in time
        ((scans("Delhi", 13, 13, count=21),), True),
        ((scans("Delhi", 13, 13, count=20),), False),
        ((scans("Delhi", 13, 13), scans("Atlantis", 14, 14)), False),  # an unknown city never decides anything
    ],
)
def test_scan_spread(stats, expect):
    assert ("SCAN_SPREAD" in codes(facts(scan_stats=stats))) is expect


@pytest.mark.parametrize(
    "product, conf, expect",
    [(PRODUCT, 0.85, True), (PRODUCT, 0.7, False), (PRODUCT.model_copy(update={"storage_max_c": 25}), 0.95, False), (PRODUCT.model_copy(update={"storage_max_c": None}), 0.95, False)],
)
def test_cold_chain_only_for_cold_products_and_confident_links(product, conf, expect):
    f = facts(product=product, doc_signals=(doc("temperature_excursion", conf, detail={"max_c": 12.0}),))
    assert ("COLD_CHAIN" in codes(f)) is expect


def complaints(n, cities, labels=("suspected_fake",), same_reporter=False, conf=0.9):
    return tuple(doc("complaint", conf, doc_id=f"c{i}", labels=labels, city=cities[i % len(cities)],
                     reporter_key="same" if same_reporter else f"r{i}") for i in range(n))  # fmt: skip


@pytest.mark.parametrize(
    "signals, expect",
    [
        (complaints(3, ["Delhi", "Mumbai"]), True),
        (complaints(1, ["Delhi"]), False),  # a single complaint changes nothing
        (complaints(2, ["Delhi", "Mumbai"]), False),
        (complaints(3, ["Delhi"]), False),  # one city
        (complaints(3, ["Delhi", "Mumbai"], same_reporter=True), False),  # one person three times
        (complaints(3, ["Delhi", "Mumbai"], labels=("delay",)), False),
        (complaints(3, ["Delhi", "Mumbai"], conf=0.7), False),
    ],
)
def test_complaint_cluster(signals, expect):
    f = facts(doc_signals=signals)
    assert ("COMPLAINT_CLUSTER" in codes(f)) is expect
    assert not {r.strength for r in reasons(f)} & {"do_not_use"}  # allegations never raise a do-not-use reason


def test_text_contradiction_is_caution_and_needs_a_confident_link():
    assert "TEXT_CONTRADICTION" in codes(facts(doc_signals=(doc("contradiction", 0.9),)))
    assert "TEXT_CONTRADICTION" not in codes(facts(doc_signals=(doc("contradiction", 0.6),)))


def test_missing_sources_are_cannot_check_and_name_who():
    r = reasons(facts(missing=("regulator",)))
    assert [(x.code, x.strength) for x in r] == [("SOURCE_MISSING", "cannot_check")]
    assert "Drug Control" in r[0].text
    gap = Hop("dist-south", "distributor", NAMES["dist-south"], CITY["dist-south"], None, "timeout")
    assert codes(facts(chain=(normal_chain()[0], gap))) == ["SOURCE_MISSING"]


def test_reasons_come_in_the_plans_order():
    f = facts(batch_status="recalled", expiry=date(2026, 1, 1), licences=(licence("shop-delhi", "suspended"),),
              missing=("regulator",))  # fmt: skip
    assert codes(f) == ["RECALLED", "EXPIRED", "UNLICENSED_HOLDER", "SOURCE_MISSING"]


def test_helpers_are_used():
    assert LOT and TODAY and at(1) and normal_chain()
