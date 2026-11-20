"""Phase 2: noise in recorded data is found, a fix is proposed from the context, and applying it leaves a trail."""

from datetime import datetime

from asali_codes.candidates import serial_candidates
from asali_codes.evaluate import make_population
from asali_node.canonical import IST, NewReceipt, UnitRef

G = "08901003000111"
AT = datetime(2026, 11, 5, 14, 7, 41, tzinfo=IST)
POP = [s for s in make_population(400, 11) if s.startswith("KS") and "S" in s[2:]]
TRUE, CLEAN = POP[0], POP[1]
NOISY = TRUE[:2] + TRUE[2:].replace("S", "5", 1)  # a look-alike slip that breaks the check character
FOREIGN = "ZZ" + CLEAN[2:]  # a prefix no maker uses
LOT = "K/26/0001"


def shop(make_node, existing):
    n = make_node("shop")
    n.rw.record_receipt(NewReceipt(from_org="dist-south", source_ref="D1", at=AT, by="asha", units=[
        UnitRef(gtin=G, serial=NOISY, lot=LOT), UnitRef(gtin=G, serial=CLEAN, lot=LOT), UnitRef(gtin=G, serial=FOREIGN, lot=LOT)]))  # fmt: skip
    a = n.share.answers
    a[("kesar", "/share/v1/units/exists")] = {"existing": existing}
    for s in existing:
        a[("kesar", f"/share/v1/units/by-serial/{s}")] = {
            "gtin": G,
            "serial": s,
            "known": True,
            "lot": LOT,
            "expiry": "2027-03-31",
        }
    n.login()
    return n


def test_noise_in_the_recorded_codes_is_found_and_clean_codes_are_not(make_node):
    n = shop(make_node, [TRUE, CLEAN])
    body = n.client.get("/api/quality").json()
    found = {a["value"]: a["problems"] for a in body["anomalies"]}
    assert set(found) == {NOISY, FOREIGN}
    assert "check character does not match" in " ".join(found[NOISY])
    assert "no maker issues codes starting ZZ" in " ".join(found[FOREIGN])
    assert body["checked"] == 3


def test_a_fix_is_proposed_only_when_an_issued_code_is_close_and_the_lot_agrees(make_node):
    n = shop(make_node, [TRUE, CLEAN])
    body = n.client.get("/api/quality").json()
    noisy = next(a for a in body["anomalies"] if a["value"] == NOISY)
    assert noisy["proposal"]["serial"] == TRUE
    assert noisy["proposal"]["cost"] <= 1.0
    foreign = next(a for a in body["anomalies"] if a["value"] == FOREIGN)
    assert foreign["proposal"] is None  # nothing issued is close: left for a person


def test_applying_a_fix_changes_the_record_and_leaves_an_audit_trail(make_node):
    n = shop(make_node, [TRUE, CLEAN])
    r = n.client.post("/api/quality/apply", json={"from_serial": NOISY, "to_serial": TRUE})
    assert r.status_code == 200 and r.json()["rows_changed"] >= 1
    again = n.client.get("/api/quality").json()
    assert NOISY not in {a["value"] for a in again["anomalies"]}
    table, _at, raw, _field, chosen, _cost, by = n.rw.CORR  # each organisation names its own correction table
    trail = n.rw.db.rows(f"SELECT {raw}, {chosen}, {by} FROM {table}")
    assert (NOISY, TRUE, "asha") in [tuple(x) for x in trail]


def test_a_fix_to_a_code_nobody_issued_is_refused(make_node):
    n = shop(make_node, [CLEAN])  # the maker does not know TRUE
    r = n.client.post("/api/quality/apply", json={"from_serial": NOISY, "to_serial": TRUE})
    assert r.status_code == 409
    assert NOISY in {a["value"] for a in n.client.get("/api/quality").json()["anomalies"]}


def test_a_fix_that_is_not_close_to_what_was_recorded_is_refused(make_node):
    far = next(s for s in POP if all(s != c.value for c in serial_candidates(NOISY, {"KS"}, max_cost=3.0)))
    n = shop(make_node, [far])
    assert (
        n.client.post("/api/quality/apply", json={"from_serial": NOISY, "to_serial": far}).status_code == 409
    )


def test_it_needs_a_login(make_node):
    n = make_node("shop")
    assert n.client.get("/api/quality").status_code == 401
    assert n.client.post("/api/quality/apply", json={"from_serial": "A", "to_serial": "B"}).status_code == 401
