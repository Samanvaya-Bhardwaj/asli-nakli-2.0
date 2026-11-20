import pytest
from asali_node.verify.rules import reasons
from asali_node.verify.text_checks import check_buying_claims, check_temperature, signals_for
from builders import LOT, G, S, facts

UNIT = f"unit:{G}/{S}"
BATCH = f"batch:{G}/{LOT}"


def complaint(city="Mumbai", shop="shop-mumbai", date="2026-11-03"):
    claims = [
        {"name": "purchase_city", "value": city},
        {"name": "purchase_shop", "value": shop},
        {"name": "purchase_date", "value": date},
    ]
    return {"id": "c1", "org_id": "consumer-mumbai", "doc_type": "consumer_complaint", "kind": "allegation", "body": "text",
            "claims": claims, "issue_labels": ["suspected_fake"], "meta": {"city": "Mumbai"}}  # fmt: skip


def test_a_complaint_about_this_exact_pack_that_names_another_city_contradicts_the_sale():
    sigs, checks = signals_for(complaint(), facts(), 0.95, "kesar", UNIT)
    assert {s.kind for s in sigs} == {"complaint", "contradiction"}
    assert {c.name: c.check for c in checks}["purchase_city"] == "contradicts"
    assert "Says bought in Mumbai" in next(s.quote for s in sigs if s.kind == "contradiction")


def test_a_complaint_about_the_batch_says_nothing_about_this_packs_sale():
    sigs, _ = signals_for(complaint(), facts(), 0.95, "kesar", BATCH)
    assert [s.kind for s in sigs] == ["complaint"]


def test_a_complaint_that_matches_the_sale_is_consistent():
    _, checks = signals_for(complaint("Delhi", "shop-delhi", "2026-11-12"), facts(), 0.95, "kesar", UNIT)
    assert {c.check for c in checks} == {"consistent"}


def test_a_city_where_the_pack_was_also_sold_is_not_a_contradiction():
    from builders import ev

    f = facts(other_sells=(ev("shop-mumbai", "sell", 14, ref="B9"),))
    assert {c.name: c.check for c in check_buying_claims(complaint()["claims"], f)}[
        "purchase_city"
    ] == "consistent"


def test_no_sale_on_record_means_unknown_not_contradicts():

    from builders import hop

    f = facts(chain=(hop("kesar", "pharma", []),))
    assert {c.check for c in check_buying_claims(complaint()["claims"], f)} == {"unknown"}


@pytest.mark.parametrize(
    "peak, readings, stated, expect",
    [
        (14.2, [], 200, "excursion"),
        (6.5, [], None, "no_excursion"),
        (
            14.2,
            [{"minute": 1, "temp_c": 5.0}, {"minute": 90, "temp_c": 14.2}, {"minute": 200, "temp_c": 14.0}],
            None,
            "excursion",
        ),
    ],
)
def test_temperature_claims_against_the_product_limit(peak, readings, stated, expect):
    claims = [{"name": "max_temp_c", "value": peak}, {"name": "readings", "value": readings}] + (
        [{"name": "stated_minutes", "value": stated}] if stated else []
    )
    r = check_temperature(claims, facts())
    assert r is not None and r.check == expect


def test_a_notice_row_for_this_lot_and_maker_is_a_full_match_and_raises_quality_failed():
    hit = {"id": "n1", "org_id": "regulator", "doc_type": "nsq_alert", "kind": "official", "body": "Drugs declared not of standard quality",
           "claims": [{"name": "row", "value": {"lot": LOT, "manufacturer": "kesar", "reason": "Dissolution failed"}}]}  # fmt: skip
    sigs, checks = signals_for(hit, facts(), 0.95, "kesar", BATCH)
    assert (
        checks[0].check == "match"
        and sigs[0].kind == "official_quality_notice"
        and sigs[0].confidence == 0.95
    )
    from dataclasses import replace

    assert "QUALITY_FAILED" in [r.code for r in reasons(replace(facts(), doc_signals=tuple(sigs)))]


def test_a_notice_naming_only_the_lot_is_a_partial_match_and_stays_below_the_do_not_use_line():
    hit = {"id": "n2", "org_id": "regulator", "doc_type": "nsq_alert", "kind": "official", "body": "x",
           "claims": [{"name": "row", "value": {"lot": LOT, "manufacturer": "tarang", "reason": "Assay low"}}]}  # fmt: skip
    sigs, _ = signals_for(hit, facts(), 0.97, "kesar", BATCH)
    assert sigs[0].confidence == 0.85
    from dataclasses import replace

    codes = [r.code for r in reasons(replace(facts(), doc_signals=tuple(sigs)))]
    assert "QUALITY_FAILED" not in codes and "QUALITY_NOTICE_POSSIBLE" in codes


def test_a_notice_for_another_lot_gives_nothing():
    hit = {"id": "n3", "org_id": "regulator", "doc_type": "nsq_alert", "kind": "official", "body": "x",
           "claims": [{"name": "row", "value": {"lot": "OTHER", "manufacturer": "kesar", "reason": "r"}}]}  # fmt: skip
    assert signals_for(hit, facts(), 0.99, "kesar", BATCH) == ([], [])


def test_a_complaint_that_names_only_the_product_is_not_counted_against_this_batch():
    sigs, _ = signals_for(complaint(), facts(), 0.95, "kesar", "product:kesar-cough")
    assert [s for s in sigs if s.kind == "complaint"] == []
