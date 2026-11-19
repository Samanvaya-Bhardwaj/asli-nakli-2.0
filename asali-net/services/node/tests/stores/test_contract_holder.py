from datetime import date, datetime, timedelta

import pytest
from asali_node.canonical import IST, NewReceipt, NewReturn, NewSale, NewShipment, SaleLine, UnitRef
from asali_node.stores.protocols import NotSupported

KINDS = ("distributor", "shop")
AT = datetime(2026, 11, 3, 9, 0, tzinfo=IST)
GTIN = "08901001000124"
SN = [f"TP{i:09d}" for i in range(1, 4)]
REF_KEEPERS = {"shop-delhi", "dist-south"}  # these two keep lot and expiry next to each scanned pack


@pytest.fixture
def held(env):
    s = env.rw()
    s.record_receipt(NewReceipt(from_org="tarang", source_ref="SHP-1", at=AT, by="ravi",
                                units=[UnitRef(gtin=GTIN, serial=x, lot="LOT-001", expiry=date(2028, 9, 30))
                                       for x in SN]))  # fmt: skip
    return s, env.spec.kind


def test_receipt_puts_units_in_stock(held, env):
    s, _ = held
    assert s.received_refs() == {("tarang", "SHP-1")}
    assert sorted(x.serial for x in s.stock()) == SN
    v = s.unit_view(GTIN, SN[0])
    assert v.known and v.status_here == "in_stock"
    (e,) = v.events
    assert (e.event_type, e.from_org, e.ref, e.org_id) == ("receive", "tarang", "SHP-1", env.spec.org_id)
    assert e.at.utcoffset() == timedelta(hours=5, minutes=30)
    if env.spec.org_id in REF_KEEPERS:
        assert s.stock()[0].lot == "LOT-001" and s.stock()[0].expiry == date(2028, 9, 30)


def test_unknown_unit(held):
    s, _ = held
    v = s.unit_view(GTIN, "ZZ000000000")
    assert (v.known, v.status_here, v.events) == (False, "never_held", [])


def test_distributor_dispatch(held):
    s, kind = held
    d = NewShipment(shipment_id="DSP-1", to_org="shop-delhi", at=AT + timedelta(hours=3), by="ravi",
                    units=[UnitRef(gtin=GTIN, serial=x) for x in SN[:2]])  # fmt: skip
    if kind == "shop":
        with pytest.raises(NotSupported):
            s.record_dispatch(d)
        assert s.shipments_to("shop-delhi") == []
        return
    out = s.record_dispatch(d)
    assert len(out.units) == 2 and out.to_org == "shop-delhi"
    (sh,) = s.shipments_to("shop-delhi")
    assert len(sh.units) == 2
    assert s.shipments_to("shop-mumbai") == []
    v = s.unit_view(GTIN, SN[0])
    assert v.status_here == "shipped" and [e.event_type for e in v.events] == ["receive", "ship"]
    assert v.events[1].to_org == "shop-delhi"
    assert [x.serial for x in s.stock()] == SN[2:]
    with pytest.raises(ValueError):  # already dispatched
        s.record_dispatch(d.model_copy(update={"shipment_id": "DSP-2"}))


def test_shop_sale_and_return(held):
    s, kind = held
    sale = NewSale(
        bill_no="B-1", at=AT + timedelta(days=1), lines=[SaleLine(gtin=GTIN, serial=SN[0], mrp_paise=12500)]
    )
    if kind == "distributor":
        with pytest.raises(NotSupported):
            s.record_sale(sale)
        with pytest.raises(NotSupported):
            s.record_return(NewReturn(bill_no="B-1", gtin=GTIN, serial=SN[0], reason="x", at=AT))
        return
    s.record_sale(sale)
    v = s.unit_view(GTIN, SN[0])
    assert v.status_here == "sold" and [e.event_type for e in v.events] == ["receive", "sell"]
    assert v.events[1].ref == "B-1"
    assert sorted(x.serial for x in s.stock()) == SN[1:]
    with pytest.raises(ValueError):  # not in stock any more
        s.record_sale(sale.model_copy(update={"bill_no": "B-2"}))
    s.record_return(
        NewReturn(bill_no="B-1", gtin=GTIN, serial=SN[0], reason="wrong strength", at=AT + timedelta(days=2))
    )
    v = s.unit_view(GTIN, SN[0])
    assert v.status_here == "returned" and v.events[-1].event_type == "return"
    with pytest.raises(ValueError):  # never sold
        s.record_return(
            NewReturn(bill_no="B-9", gtin=GTIN, serial=SN[1], reason="x", at=AT + timedelta(days=2))
        )
