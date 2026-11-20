"""Phase 2: every issued code that approximately matches a noisy reading, and every noisy reading of an issued code."""

from asali_codes.candidates import serial_candidates
from asali_codes.evaluate import make_population
from asali_node.canonical import StaffRecord

G = "08901003000111"
TRUE = next(s for s in make_population(400, 3) if s.startswith("KS") and "S" in s[2:])
NOISY = TRUE[:2] + TRUE[2:].replace("S", "5", 1)
OTHERS = [c for c in serial_candidates(NOISY, {"KS"}, max_cost=2.0) if c.value != TRUE]


class Reg:
    def __init__(self):
        self.staff = {}

    def init_schema(self): ...
    def get_staff(self, u):
        return self.staff.get(u)

    def add_staff(self, r: StaffRecord):
        self.staff[r.username] = r

    def alerts(self, *a, **k):
        return []

    def licences(self, *a, **k):
        return []


def node(make_node, existing, lots):
    n = make_node("regulator", store=Reg())
    n.client.app.state.directory.orgs = [*n.client.app.state.directory.orgs,
        {"org_id": "consumer-delhi", "org_type": "consumer", "name": "Asali Check", "city": "Delhi", "state": "DL", "host_name": "PC-A", "issuer_code": None, "online": True}]  # fmt: skip
    a = n.share.answers
    a[("kesar", "/share/v1/units/exists")] = {"existing": existing}
    a[("kesar", "/share/v1/products")] = {
        "products": [
            {"gtin": G, "brand": "Glargikes", "generic": "insulin glargine", "strength": "100 IU/ml"}
        ]
    }
    for s in existing:
        a[("kesar", f"/share/v1/units/by-serial/{s}")] = {
            "gtin": G,
            "serial": s,
            "known": True,
            "lot": lots[s],
            "expiry": "2027-03-31",
        }
    n.login()
    return n


def test_every_issued_code_near_the_reading_is_listed_cheapest_first_with_its_record(make_node):
    other = OTHERS[0].value
    n = node(make_node, [TRUE, other], {TRUE: "K/26/0001", other: "K/26/0002"})
    body = n.client.post("/api/similar", json={"raw": NOISY}).json()
    costs = [m["cost"] for m in body["matches"]]
    assert costs == sorted(costs)
    assert {m["serial"] for m in body["matches"]} == {TRUE, other}
    mine = next(m for m in body["matches"] if m["serial"] == TRUE)
    assert (mine["lot"], mine["product"]) == ("K/26/0001", "Glargikes 100 IU/ml")
    assert any("5" in e and "S" in e for e in mine["edits"])


def test_the_lot_on_the_label_is_reported_as_fitting_or_not_for_each_match(make_node):
    other = OTHERS[0].value
    n = node(make_node, [TRUE, other], {TRUE: "K/26/0001", other: "K/26/0002"})
    raw = f"https://id.asali.example/01/{G}/21/{NOISY}?10=K/26/0002"
    by = {
        m["serial"]: m["fits_label"]
        for m in n.client.post("/api/similar", json={"raw": raw}).json()["matches"]
    }
    assert by == {TRUE: False, other: True}


def test_noisy_readings_recorded_against_an_issued_code_are_listed_as_the_other_direction(make_node):
    n = node(make_node, [TRUE], {TRUE: "K/26/0001"})
    n.share.answers[("consumer-delhi", f"/share/v1/scans/{G}/{TRUE}/inputs")] = {"inputs": [
        {"raw_input": TRUE, "city": "Delhi", "at": "2026-11-10T10:00:00+05:30"},
        {"raw_input": NOISY, "city": "Delhi", "at": "2026-11-11T10:00:00+05:30"},
    ]}  # fmt: skip
    body = n.client.post("/api/similar", json={"raw": TRUE}).json()
    assert [s["raw_input"] for s in body["seen_as"]] == [NOISY]  # the exact reading is not a variant
    assert body["seen_as"][0]["cost"] > 0 and body["seen_as"][0]["edits"]


def test_a_reading_nothing_resembles_gives_empty_lists_not_an_error(make_node):
    n = node(make_node, [], {})
    body = n.client.post("/api/similar", json={"raw": "KSZZZZZZZZZ"}).json()
    assert body["matches"] == [] and body["seen_as"] == []


def test_it_needs_a_login(make_node):
    n = make_node("regulator", store=Reg())
    assert n.client.post("/api/similar", json={"raw": NOISY}).status_code == 401
