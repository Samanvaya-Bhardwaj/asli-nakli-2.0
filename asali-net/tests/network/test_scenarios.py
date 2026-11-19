"""Seeded scenarios against the running network. Simulation on one computer: it proves behaviour, not distribution."""

import pytest

pytestmark = pytest.mark.network


def check(consumer, raw, city="Delhi"):
    r = consumer.post("/api/check", json={"raw": raw, "city": city})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("name", ["S1", "S2", "S3", "S4", "S7"])
def test_scenario_gives_the_expected_verdict_and_reasons(name, consumer, scenarios, expected):
    body = check(consumer, scenarios[name]["raw"])
    assert body["status"] == "done", body
    result = body["result"]
    assert result["verdict"] == expected[name]["verdict"], result["headline"]
    assert [r["code"] for r in result["reasons"]] == expected[name]["reasons"]
    assert result["mode"] == "simulation"


def test_s1_history_names_each_organisation_and_its_computer(consumer, scenarios):
    result = check(consumer, scenarios["S1"]["raw"])["result"]
    assert len(result["history"]) >= 3
    assert all(h["served_by"] and h["served_by"]["host_name"] == "SIM-LOCAL" for h in result["history"])
    assert "Genuine." in result["headline"] and result["sources"]


def test_s9_a_misread_needs_confirmation_then_gives_the_s1_result(consumer, scenarios, expected):
    q = check(consumer, scenarios["S9"]["raw"])
    assert q["status"] == expected["S9"]["status"] and q["serial"] == scenarios["S9"]["true_serial"]
    done = consumer.post("/api/check/confirm", json={"check_id": q["check_id"], "serial": q["serial"]}).json()
    assert done["result"]["verdict"] == "genuine" and done["result"]["read"]["confirmed"] is True


def test_a_wrong_confirmation_is_refused(consumer, scenarios):
    q = check(consumer, scenarios["S9"]["raw"])
    r = consumer.post("/api/check/confirm", json={"check_id": q["check_id"], "serial": "KS000000000"})
    assert r.status_code == 404


def test_s8_a_stopped_distributor_on_the_route_means_cannot_check(consumer, scenarios):
    import sim_control

    route_west = scenarios["S8"]
    sim_control.stop_org("dist-west")
    try:
        result = check(consumer, route_west["raw"])["result"]
    finally:
        sim_control.start_org("dist-west")
    assert result["verdict"] == "cannot_check", result["headline"]
    assert "Western Medilink did not answer" in result["headline"]
    assert any(s["org_id"] == "dist-west" and s["status"] != "answered" for s in result["sources"])
    again = check(consumer, route_west["raw"])["result"]
    assert again["verdict"] != "cannot_check"
