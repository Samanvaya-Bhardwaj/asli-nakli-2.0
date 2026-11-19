from datetime import datetime

import pytest
from asali_node.canonical import IST, Alert, NewAlert, NewCheck, StaffRecord

AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
GTIN, SERIAL = "08901003000111", "KS000000001"


class Explode:
    """Stands in for the read-write store: any use from a share route fails the test."""

    def __getattr__(self, name):
        raise AssertionError(f"a share route used the read-write store ({name})")


class RegStore:
    def __init__(self):
        self.items, self.staff = [], {}

    def init_schema(self): ...
    def get_staff(self, u):
        return self.staff.get(u)

    def add_staff(self, r: StaffRecord):
        self.staff[r.username] = r

    def add_alert(self, a: NewAlert):
        al = Alert(alert_id=f"A{len(self.items)}", **a.model_dump())
        self.items.append(al)
        return al

    def alerts(self, gtin=None, lot=None, state=None):
        return [
            a
            for a in self.items
            if (gtin is None or a.gtin == gtin) and (state is None or a.states is None or state in a.states)
        ]

    def licences(self, org_ids=None):
        return []


def test_share_routes_use_only_the_read_only_store(make_node):
    n = make_node("pharma")
    n.client.app.state.rw = Explode()
    assert n.signed_get("/share/v1/products").status_code == 200
    assert n.signed_get("/share/v1/batches").status_code == 200
    assert n.signed_get(f"/share/v1/units/{GTIN}/{SERIAL}").json()["known"] is False
    assert n.signed_get(f"/share/v1/units/exists?gtin={GTIN}&serials={SERIAL}").json() == {"existing": []}
    assert n.signed_get("/share/v1/shipments").json() == {"shipments": []}
    assert n.signed_get(f"/share/v1/units/by-serial/{SERIAL}").status_code == 404


def test_units_carry_who_served_them(make_node):
    n = make_node("shop")
    body = n.signed_get(f"/share/v1/units/{GTIN}/{SERIAL}").json()
    assert body["served_by"]["org_id"] == "shop-delhi" and body["served_by"]["host_name"] == "PC-TEST"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_share_paths_answer_get_only(make_node, method):

    n = make_node("pharma")
    r = n.signed(method, "/share/v1/products")
    assert r.status_code == 405


def test_unsigned_share_calls_are_refused(make_node):
    assert make_node("pharma").client.get("/share/v1/products").status_code == 401


def test_a_shop_does_not_answer_catalogue_or_existence_questions(make_node):
    n = make_node("shop")
    r = n.signed_get(f"/share/v1/units/exists?gtin={GTIN}&serials={SERIAL}")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
    assert n.signed_get("/share/v1/products").status_code == 404
    assert n.signed_get("/share/v1/shipments").status_code == 404  # shops send nothing on


def test_consumer_scan_stats_hide_devices_and_seconds_and_bulk_reports_are_regulator_only(make_node):
    n = make_node("consumer")
    n.rw.record_check(NewCheck(raw_input="x", gtin=GTIN, serial=SERIAL, verdict="genuine", reasons=[], city="Delhi",
                               at=AT, device_hash="secretdevice"))  # fmt: skip
    body = n.signed_get(f"/share/v1/scans/{GTIN}/{SERIAL}").json()
    assert body["total"] == 1 and "secretdevice" not in str(body)
    assert body["by_city"][0]["first_at"].endswith("14:07:00+05:30")
    assert n.signed_get("/share/v1/reports", caller="shop-delhi").status_code == 403
    assert n.signed_get("/share/v1/reports", caller="regulator").status_code == 200


def test_regulator_alerts_by_state_and_licences(make_node):
    n = make_node("regulator", store=RegStore())
    n.rw.add_alert(
        NewAlert(
            kind="recall",
            gtin=GTIN,
            lot=None,
            manufacturer_org="kesar",
            issued_at=AT,
            reason="r",
            states=["DL"],
        )
    )
    assert len(n.signed_get(f"/share/v1/alerts?gtin={GTIN}").json()["alerts"]) == 1
    assert n.signed_get("/share/v1/alerts?state=MH").json()["alerts"] == []
    assert n.signed_get("/share/v1/licences?org_ids=a,b").json() == {"licences": []}


def test_documents_are_empty_until_the_text_pipeline_exists(make_node):
    n = make_node("shop")
    assert n.signed_get("/share/v1/documents/search").json()["hits"] == []
    assert n.signed_get("/share/v1/documents/nope").status_code == 404
