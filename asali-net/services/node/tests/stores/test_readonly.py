"""The read-only account of every organisation's database refuses to write, at the database."""

from datetime import date, datetime

import pytest
from asali_node.canonical import (
    IST,
    NewAlert,
    NewCheck,
    NewProduct,
    NewReceipt,
    StaffRecord,
    UnitRef,
)  # fmt: skip

AT = datetime(2026, 11, 3, 9, 0, tzinfo=IST)


def a_write(kind, store):
    if kind == "pharma":
        store.add_product(NewProduct(gtin="08901001000124", brand="B", generic="g", strength="5 mg", form="tablet",
                                     pack_size=10))  # fmt: skip
    elif kind in ("distributor", "shop"):
        store.record_receipt(NewReceipt(from_org="tarang", source_ref="S1", at=AT, by="x",
                                        units=[UnitRef(gtin="08901001000124", serial="TP000000001",
                                                       lot="L", expiry=date(2028, 1, 31))]))  # fmt: skip
    elif kind == "consumer":
        store.record_check(
            NewCheck(raw_input="x", gtin=None, serial=None, verdict=None, reasons=[], city="Delhi", at=AT)
        )
    else:
        store.add_alert(NewAlert(kind="recall", gtin="08901001000124", lot=None, manufacturer_org="tarang",
                                 issued_at=AT, reason="r"))  # fmt: skip


def refused(engine, exc: BaseException) -> bool:
    if engine == "pg":
        import psycopg.errors

        return isinstance(exc, psycopg.errors.InsufficientPrivilege)
    if engine == "mongo":
        from pymongo.errors import OperationFailure

        return isinstance(exc, OperationFailure) and exc.code == 13
    import sqlite3

    return isinstance(exc, sqlite3.OperationalError) and "readonly" in str(exc)


def test_ro_store_cannot_write_entities(env):
    env.rw().close()  # schema exists, nothing else
    ro = env.ro()
    with pytest.raises(Exception) as caught:
        a_write(env.spec.kind, ro)
    assert refused(env.spec.engine, caught.value), repr(caught.value)


def test_ro_store_cannot_add_staff(env):
    env.rw().close()
    ro = env.ro()
    with pytest.raises(Exception) as caught:
        ro.add_staff(StaffRecord(username="x", password_hash="h", role="admin", display_name="X"))
    assert refused(env.spec.engine, caught.value), repr(caught.value)


def test_ro_store_still_reads(env):
    rw = env.rw()
    rw.add_staff(StaffRecord(username="x", password_hash="h", role="operator", display_name="X"))
    ro = env.ro()
    got = ro.get_staff("x")
    assert got is not None and got.role == "operator"
