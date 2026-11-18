from datetime import date, datetime

import pytest
from asali_node.canonical import IST, Batch, Event, UnitRef, UnitView
from pydantic import ValidationError


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        Event(event_id="e1", org_id="tarang", event_type="commission", at=datetime(2026, 11, 1, 10, 0),
              gtin="08901001000124", serial="TPM9S346Q37", city="Baddi")  # fmt: skip


def test_aware_datetimes_are_accepted():
    e = Event(event_id="e1", org_id="tarang", event_type="ship", at=datetime(2026, 11, 1, 10, 0, tzinfo=IST),
              gtin="08901001000124", serial="TPM9S346Q37", to_org="dist-north", city="Baddi")  # fmt: skip
    assert e.at.utcoffset().total_seconds() == 5.5 * 3600


@pytest.mark.parametrize("bad", [{"event_type": "teleport"}, {"status": "lost"}])
def test_literals_are_enforced(bad):
    base_event = {
        "event_id": "e", "org_id": "o", "event_type": "sell", "gtin": "g", "serial": "s", "city": "c",
        "at": datetime(2026, 1, 1, tzinfo=IST),
    }  # fmt: skip
    base_batch = {
        "gtin": "g", "lot": "l", "mfg_date": date(2026, 1, 1), "expiry_date": date(2027, 1, 31),
        "status": "released", "owner_org": "o",
    }  # fmt: skip
    with pytest.raises(ValidationError):
        if "event_type" in bad:
            Event(**{**base_event, **bad})
        else:
            Batch(**{**base_batch, **bad})


def test_models_are_frozen_and_strict():
    ref = UnitRef(gtin="g", serial="s")
    with pytest.raises(ValidationError):
        ref.serial = "x"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        UnitRef(gtin="g", serial="s", colour="red")  # type: ignore[call-arg]


def test_unit_view_for_an_unknown_pack():
    v = UnitView(
        gtin="g", serial="s", known=False, lot=None, expiry=None, status_here="never_held", events=[]
    )
    assert v.served_by is None
