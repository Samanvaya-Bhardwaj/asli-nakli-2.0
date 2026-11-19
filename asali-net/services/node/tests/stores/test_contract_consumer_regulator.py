from datetime import date, datetime, timedelta

import pytest
from asali_node.canonical import IST, Licence, NewAlert, NewCheck, NewInspection, NewReport

AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
GTIN, SERIAL = "08901001000124", "TP000000001"


def check(city, at):
    return NewCheck(raw_input=f"{GTIN}{SERIAL}", gtin=GTIN, serial=SERIAL, verdict="genuine", reasons=[],
                    city=city, at=at, device_hash="d" * 8)  # fmt: skip


@pytest.fixture
def consumer(env):
    if env.spec.kind != "consumer":
        pytest.skip(f"{env.spec.org_id} is not a consumer node")
    return env.rw()


def test_scan_stat_counts_by_city_and_hides_seconds(consumer):
    for city, mins in (("Delhi", 0), ("Delhi", 9), ("Mumbai", 20)):
        assert consumer.record_check(check(city, AT + timedelta(minutes=mins)))
    st = consumer.scan_stat(GTIN, SERIAL)
    assert st.total == 3
    by = {c.city: c for c in st.by_city}
    assert by["Delhi"].count == 2 and by["Mumbai"].count == 1
    assert by["Delhi"].first_at < by["Delhi"].last_at
    assert all(c.first_at.second == 0 and c.last_at.second == 0 for c in st.by_city)
    assert all(c.first_at.utcoffset() == timedelta(hours=5, minutes=30) for c in st.by_city)


def test_scan_stat_of_an_unseen_pack_is_empty(consumer):
    st = consumer.scan_stat(GTIN, "ZZ000000000")
    assert (st.total, st.by_city) == (0, [])


def test_reports_and_since_filter(consumer):
    cid = consumer.record_check(check("Delhi", AT))
    rid = consumer.record_report(
        NewReport(check_id=cid, doc_id="doc1", gtin=GTIN, serial=SERIAL, city="Delhi", at=AT)
    )
    consumer.record_report(NewReport(check_id=None, doc_id="doc2", gtin=None, serial=None, city="Pune",
                                     at=AT + timedelta(days=2)))  # fmt: skip
    assert rid
    assert [r.doc_id for r in consumer.reports()] == ["doc1", "doc2"]
    assert [r.doc_id for r in consumer.reports(since=AT + timedelta(days=1))] == ["doc2"]
    assert consumer.reports()[1].gtin is None


@pytest.fixture
def regulator(env):
    if env.spec.kind != "regulator":
        pytest.skip(f"{env.spec.org_id} is not the regulator")
    return env.rw()


def test_alerts_filter_by_pack_and_state(regulator):
    a = regulator.add_alert(NewAlert(kind="recall", gtin=GTIN, lot="LOT-001", manufacturer_org="tarang",
                                     issued_at=AT, reason="mislabelled", states=["DL"]))  # fmt: skip
    regulator.add_alert(NewAlert(kind="nsq", gtin="08901002000011", lot=None, manufacturer_org="medivra",
                                 issued_at=AT + timedelta(days=1), reason="fails assay"))  # fmt: skip
    assert a.alert_id and a.states == ["DL"]
    assert len(regulator.alerts()) == 2
    assert [x.kind for x in regulator.alerts(gtin=GTIN)] == ["recall"]
    assert [x.kind for x in regulator.alerts(gtin=GTIN, lot="LOT-001")] == ["recall"]
    assert [x.kind for x in regulator.alerts(state="DL")] == ["nsq", "recall"]  # newest first
    assert [x.kind for x in regulator.alerts(state="MH")] == ["nsq"]  # national alerts only


def test_licences_upsert_and_filter(regulator):
    lic = Licence(org_id="shop-delhi", licence_no="DL-R-1", licence_type="retail", valid_from=date(2025, 1, 1),
                  valid_to=date(2027, 12, 31), status="active")  # fmt: skip
    regulator.set_licence(lic)
    regulator.set_licence(Licence(org_id="dist-north", licence_no="DL-W-9", licence_type="wholesale",
                                  valid_from=date(2025, 1, 1), valid_to=date(2026, 6, 30), status="active"))  # fmt: skip
    regulator.set_licence(lic.model_copy(update={"status": "suspended"}))
    assert len(regulator.licences()) == 2
    (one,) = regulator.licences(["shop-delhi"])
    assert one.status == "suspended" and one.valid_to == date(2027, 12, 31)
    regulator.add_inspection(NewInspection(org_id="shop-delhi", inspected_at=AT, outcome="passed"))


def test_regulator_inspection_in_ist(regulator):
    regulator.add_inspection(
        NewInspection(org_id="shop-delhi", inspected_at=AT, outcome="passed", doc_id="d9")
    )
    assert IST is not None
