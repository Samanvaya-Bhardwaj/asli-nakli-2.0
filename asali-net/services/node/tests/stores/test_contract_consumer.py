from datetime import datetime, timedelta

import pytest
from asali_node.canonical import IST, NewCheck, NewReport

KINDS = ("consumer",)
AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
GTIN, SERIAL = "08901001000124", "TP000000001"


def check(city, at):
    return NewCheck(raw_input=f"{GTIN}{SERIAL}", gtin=GTIN, serial=SERIAL, verdict="genuine", reasons=[],
                    city=city, at=at, device_hash="d" * 8)  # fmt: skip


@pytest.fixture
def consumer(env):
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
