from datetime import date, datetime

from asali_node.canonical import IST, NewBatch, NewProduct

AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
GTIN, SERIAL = "08901003000111", "KS000000001"


def stocked(make_node):
    n = make_node("pharma")
    n.rw.add_product(NewProduct(gtin=GTIN, brand="Kesvir", generic="insulin glargine", strength="100 IU/mL", form="injection",
                                pack_size=1, storage_min_c=2, storage_max_c=8))  # fmt: skip
    b = n.rw.create_batch(
        NewBatch(
            gtin=GTIN,
            lot="KS-2610-001",
            mfg_date=date(2026, 10, 1),
            expiry_date=date(2028, 9, 30),
            quantity=10,
        )
    )
    n.rw.commission_units(GTIN, b.lot, [SERIAL, "KS000000002"], AT)
    n.rw.recall_batch(GTIN, b.lot, "dissolution failed in stability testing", "batch", AT)
    return n


def test_the_node_returns_terms_found_through_its_own_keys(make_node):
    n = stocked(make_node)
    body = n.signed_get(
        f"/share/v1/context?gtin={GTIN}&serial={SERIAL}&lot=KS-2610-001&kw=recall,cold%20chain"
    ).json()
    terms = " ".join(t["term"] for t in body["ranked_context"])
    assert "dissolution" in terms
    assert len(body["explored_tables"]) >= 3
    assert body["org_id"] == "kesar"


def test_it_returns_terms_and_never_rows_or_other_packs_codes(make_node):
    n = stocked(make_node)
    text = n.signed_get(f"/share/v1/context?gtin={GTIN}&serial={SERIAL}&kw=recall").text
    assert "KS000000002" not in text  # another pack in the same batch
    assert "password" not in text.lower()


def test_a_request_with_nothing_to_look_up_is_refused(make_node):
    assert stocked(make_node).signed_get("/share/v1/context").status_code == 400


def test_it_cannot_write(make_node):
    n = stocked(make_node)
    assert n.signed("POST", "/share/v1/context").status_code in (404, 405)
