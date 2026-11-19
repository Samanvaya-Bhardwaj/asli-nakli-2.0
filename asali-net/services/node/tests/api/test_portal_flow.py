"""Pharma makes packs and dispatches; a distributor receives; a shop sells and takes a return."""

from datetime import datetime

import pytest
from asali_codes.checks import gtin_is_valid, luhn32_is_valid
from asali_node import deps
from asali_node.canonical import IST, NewReceipt, UnitRef
from asali_node.problems import Problem

AT = "2026-11-02T10:00:00+05:30"


def pharma_with_packs(make_node, count=6):
    n = make_node("pharma")
    n.login()
    p = n.client.post("/api/products", json={"brand": "Amoxil-T", "generic": "amoxicillin", "strength": "500 mg",
                                             "form": "capsule", "pack_size": 10, "storage_min_c": 15, "storage_max_c": 25})  # fmt: skip
    assert p.status_code == 201
    gtin = p.json()["gtin"]
    b = n.client.post(
        "/api/batches",
        json={"gtin": gtin, "mfg_date": "2026-10-05", "expiry_date": "2028-09-30", "quantity": count},
    )
    assert b.status_code == 201
    lot = b.json()["lot"]
    assert n.client.post(f"/api/batches/{lot}/packs", json={"count": count, "at": AT}).status_code == 201
    return n, gtin, lot


def scan_all(n, kind, serials, gtin, **start):
    sid = n.client.post("/api/scan/sessions", json={"kind": kind, **start}).json()["session_id"]
    for s in serials:
        r = n.client.post(
            f"/api/scan/sessions/{sid}/read", json={"raw": f"(01){gtin}(21){s}", "source": "typed"}
        )
        assert r.json()["row"]["status"] == "ok", r.json()
    return sid


def test_pharma_serials_gtin_and_lot_follow_the_rules(make_node):
    n, gtin, lot = pharma_with_packs(make_node)
    assert gtin_is_valid(gtin) and gtin.startswith("08901003")
    assert lot.startswith("K/26/")
    labels = n.client.get(f"/api/batches/{lot}/labels").json()["labels"]
    assert len(labels) == 6 and len({x["serial"] for x in labels}) == 6
    for x in labels:
        assert x["serial"].startswith("KS") and luhn32_is_valid(x["serial"])
        assert x["digital_link"].startswith(f"https://id.asali.example/01/{gtin}/21/{x['serial']}?10=")
        assert x["line"].startswith(f"GTIN {gtin}   SN KS")


def test_dispatch_session_writes_one_shipment_the_share_api_shows(make_node):
    n, gtin, lot = pharma_with_packs(make_node)
    serials = [x["serial"] for x in n.client.get(f"/api/batches/{lot}/labels").json()["labels"]]
    sid = scan_all(n, "dispatch", serials[:3], gtin, to_org="dist-south")
    done = n.client.post(f"/api/scan/sessions/{sid}/finish", json={"at": AT}).json()
    assert done["units"] == 3 and done["shipment_id"].startswith("SHP-")
    ship = n.signed_get("/share/v1/shipments").json()["shipments"]
    assert len(ship) == 1 and len(ship[0]["units"]) == 3
    assert n.signed_get("/share/v1/shipments", caller="shop-delhi").json()["shipments"] == []


def test_a_misread_is_corrected_from_the_expected_set_and_logged(make_node):
    n, gtin, lot = pharma_with_packs(make_node)
    serials = [x["serial"] for x in n.client.get(f"/api/batches/{lot}/labels").json()["labels"]]
    s = serials[0]
    swapped = s[:5] + s[6] + s[5] + s[7:]
    assert swapped != s
    sid = n.client.post("/api/scan/sessions", json={"kind": "dispatch", "to_org": "dist-south"}).json()[
        "session_id"
    ]
    r = n.client.post(f"/api/scan/sessions/{sid}/read", json={"raw": f"(01){gtin}(21){swapped}"}).json()[
        "row"
    ]
    assert r["status"] == "corrected" and r["serial"] == s and "corrected to" in r["message"]
    n.client.post(f"/api/scan/sessions/{sid}/finish", json={"at": AT})
    assert n.rw.unit_view(gtin, s).status_here == "shipped"


def test_rows_for_unknown_duplicate_and_unreadable_codes(make_node):
    n, gtin, lot = pharma_with_packs(make_node)
    serials = [x["serial"] for x in n.client.get(f"/api/batches/{lot}/labels").json()["labels"]]
    sid = n.client.post("/api/scan/sessions", json={"kind": "dispatch", "to_org": "dist-south"}).json()[
        "session_id"
    ]
    read = lambda raw: n.client.post(f"/api/scan/sessions/{sid}/read", json={"raw": raw}).json()  # noqa: E731
    assert read(f"(01){gtin}(21){serials[0]}")["row"]["status"] == "ok"
    assert read(f"(01){gtin}(21){serials[0]}")["row"]["status"] == "duplicate"
    junk = read("hello")
    assert junk["row"]["status"] == "unreadable" and junk["needs_attention"] == 1
    r = n.client.post(f"/api/scan/sessions/{sid}/finish", json={})
    assert r.status_code == 409 and r.json()["code"] == "unresolved_rows"
    n.client.post(f"/api/scan/sessions/{sid}/rows/{junk['row']['row_id']}/undo")
    assert n.client.post(f"/api/scan/sessions/{sid}/finish", json={"at": AT}).status_code == 200
    assert n.client.get(f"/api/scan/sessions/{sid}").status_code == 410  # finished sessions are gone


def test_distributor_receives_with_a_discrepancy_then_shop_sells_and_returns(make_node):
    ph, gtin, lot = pharma_with_packs(make_node)
    serials = [x["serial"] for x in ph.client.get(f"/api/batches/{lot}/labels").json()["labels"]]
    sid = scan_all(ph, "dispatch", serials[:4], gtin, to_org="dist-south")
    shipment = ph.client.post(f"/api/scan/sessions/{sid}/finish", json={"at": AT}).json()["shipment_id"]

    dist = make_node("distributor")
    dist.login()
    dist.share.answers[("kesar", "/share/v1/shipments")] = ph.rw.shipments_to("dist-south") and {
        "shipments": [s.model_dump(mode="json") for s in ph.rw.shipments_to("dist-south")]
    }
    inc = dist.client.get("/api/incoming").json()
    assert inc["incoming"][0]["shipment_id"] == shipment and inc["incoming"][0]["count"] == 4
    assert {"org_id": "kesar", "status": "answered", "reason": ""} in inc["sources"]

    rid = scan_all(dist, "receive", serials[:3], gtin, from_org="kesar", source_ref=shipment)
    got = dist.client.post(f"/api/scan/sessions/{rid}/finish", json={"at": AT}).json()
    assert got["received"] == 3 and got["missing"] == [serials[3]]
    assert dist.client.get("/api/incoming").json()["incoming"] == []
    assert dist.client.get("/api/stock").json()["total"] == 3
    assert (
        dist.client.post(
            "/api/scan/sessions", json={"kind": "receive", "from_org": "kesar", "source_ref": shipment}
        ).status_code
        == 409
    )

    shop = make_node("shop")
    shop.login()
    shop.rw.record_receipt(NewReceipt(from_org="dist-south", source_ref="DSP-1", at=datetime(2026, 11, 1, tzinfo=IST),
                                      by="x", units=[UnitRef(gtin=gtin, serial=serials[0])]))  # fmt: skip
    sell = scan_all(shop, "sell", [serials[0]], gtin)
    assert (
        shop.client.post(f"/api/scan/sessions/{sell}/finish", json={"at": AT}).status_code == 422
    )  # no price
    sell = scan_all(shop, "sell", [serials[0]], gtin)
    sold = shop.client.post(
        f"/api/scan/sessions/{sell}/finish",
        json={"at": AT, "prices": {gtin: 12500}, "customer_last4": "4321"},
    ).json()
    assert sold["total_paise"] == 12500 and sold["bill_no"].startswith("B-")
    back = scan_all(shop, "return", [serials[0]], gtin)
    assert (
        shop.client.post(
            f"/api/scan/sessions/{back}/finish", json={"at": AT, "reason": "wrong strength"}
        ).status_code
        == 200
    )
    assert shop.rw.unit_view(gtin, serials[0]).status_here == "returned"


def test_a_portal_cannot_start_another_roles_session(make_node):
    shop = make_node("shop")
    shop.login()
    r = shop.client.post("/api/scan/sessions", json={"kind": "dispatch", "to_org": "x"})
    assert r.status_code == 403 and r.json()["code"] == "wrong_portal"


def test_incoming_names_the_upstream_node_that_did_not_answer(make_node):
    dist = make_node("distributor")
    dist.login()
    body = dist.client.get("/api/incoming").json()  # the fake pharma gives no answer
    assert body["incoming"] == []
    assert body["sources"] == [{"org_id": "kesar", "status": "unreachable", "reason": "unreachable"}]


def test_time_cannot_be_set_outside_simulation(make_node):
    n = make_node("pharma")
    request = type("R", (), {"app": n.client.app})()
    n.client.app.state.settings = n.settings.model_copy(update={"asali_mode": "network"})
    with pytest.raises(Problem):
        deps.effective_at(request, datetime(2026, 1, 1, tzinfo=IST))  # type: ignore[arg-type]
    assert deps.effective_at(request, None).tzinfo is not None  # type: ignore[arg-type]
