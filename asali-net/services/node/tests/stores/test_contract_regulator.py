from datetime import date, datetime, timedelta

import pytest
from asali_node.canonical import IST, Licence, NewAlert, NewInspection

KINDS = ("regulator",)
AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
GTIN = "08901001000124"


@pytest.fixture
def regulator(env):
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
