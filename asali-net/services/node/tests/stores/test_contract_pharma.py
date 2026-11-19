from datetime import date, datetime, timedelta

import pytest
from asali_node.canonical import IST, NewBatch, NewProduct, NewShipment, UnitRef

KINDS = ("pharma",)
AT = datetime(2026, 11, 2, 10, 30, tzinfo=IST)
GTIN = "08901001000124"


@pytest.fixture
def store(env):
    return env.rw()


def serials(env, n=5):
    issuer = {"tarang": "TP", "medivra": "MV", "kesar": "KS"}[env.spec.org_id]
    return [f"{issuer}{i:09d}" for i in range(1, n + 1)]


@pytest.fixture
def stocked(store, env):
    store.add_product(NewProduct(gtin=GTIN, brand="Amoxil-T", generic="amoxicillin", strength="500 mg",
                                 form="capsule", pack_size=10, storage_min_c=15, storage_max_c=25))  # fmt: skip
    store.create_batch(NewBatch(gtin=GTIN, lot="LOT-001", mfg_date=date(2026, 10, 5),
                                expiry_date=date(2028, 9, 30), quantity=5))  # fmt: skip
    sn = serials(env)
    assert store.commission_units(GTIN, "LOT-001", sn, AT) == 5
    ship = store.record_shipment(NewShipment(
        shipment_id="SHP-1", to_org="dist-north", at=AT + timedelta(hours=2), by="asha",
        units=[UnitRef(gtin=GTIN, serial=s) for s in sn[:3]], vehicle_no="DL1CAB1234"))  # fmt: skip
    return store, sn, ship


def test_catalogue_round_trip(stocked):
    store, _, _ = stocked
    (p,) = store.products()
    assert (p.gtin, p.generic, p.strength, p.form, p.pack_size) == (
        GTIN,
        "amoxicillin",
        "500 mg",
        "capsule",
        10,
    )
    assert (p.storage_min_c, p.storage_max_c) == (15, 25)
    (b,) = store.batches(GTIN)
    assert (b.lot, b.mfg_date, b.expiry_date, b.status) == (
        "LOT-001",
        date(2026, 10, 5),
        date(2028, 9, 30),
        "released",
    )
    assert store.batches("08901001999999") == []


def test_shipped_unit_has_commission_and_ship_events(stocked):
    store, sn, ship = stocked
    v = store.unit_view(GTIN, sn[0])
    assert v.known and v.status_here == "shipped" and v.lot == "LOT-001" and v.expiry == date(2028, 9, 30)
    assert [e.event_type for e in v.events] == ["commission", "ship"]
    assert v.events[1].to_org == "dist-north" and v.events[1].ref == "SHP-1"
    assert ship.shipment_id == "SHP-1" and len(ship.units) == 3


def test_unshipped_and_unknown_units(stocked):
    store, sn, _ = stocked
    assert store.unit_view(GTIN, sn[4]).status_here == "in_stock"
    v = store.unit_view(GTIN, "ZZ000000000")
    assert (v.known, v.status_here, v.events) == (False, "never_held", [])


def test_shipments_to_and_stock(stocked):
    store, sn, _ = stocked
    (s,) = store.shipments_to("dist-north")
    assert len(s.units) == 3 and s.from_org == store.org_id
    assert store.shipments_to("dist-west") == []
    assert store.shipments_to("dist-north", since=AT + timedelta(days=1)) == []
    assert sorted(x.serial for x in store.stock()) == sn[3:]


def test_existing_serials_only_real_ones(stocked):
    store, sn, _ = stocked
    asked = [*sn[:2], "ZZ000000000", "ZZ000000001"]
    assert store.existing_serials(GTIN, asked) == set(sn[:2])
    assert store.existing_serials(None, asked) == set(sn[:2])
    assert store.existing_serials("08901001999999", asked) == set()


def test_times_are_aware_and_in_ist(stocked):
    store, sn, _ = stocked
    for e in store.unit_view(GTIN, sn[0]).events:
        assert e.at.utcoffset() == timedelta(hours=5, minutes=30)
    assert store.shipments_to("dist-north")[0].at.tzinfo is not None
    assert store.stock()[0].since.utcoffset() == IST.utcoffset(AT)  # type: ignore[union-attr]


def test_a_shipped_serial_cannot_ship_again_and_unknown_lot_is_refused(stocked):
    store, sn, _ = stocked
    with pytest.raises(ValueError):
        store.record_shipment(NewShipment(shipment_id="SHP-2", to_org="dist-west", at=AT, by="a",
                                          units=[UnitRef(gtin=GTIN, serial=sn[0])]))  # fmt: skip
    with pytest.raises(ValueError):
        store.commission_units(GTIN, "NO-SUCH-LOT", ["XX000000001"], AT)


def test_recall_changes_batch_status(stocked):
    store, _, _ = stocked
    store.recall_batch(GTIN, "LOT-001", "failed dissolution", "class II", AT + timedelta(days=3))
    assert store.batches(GTIN)[0].status == "recalled"
