from asali_node.canonical import Alert, NewAlert, StaffRecord

AT = "2026-11-05T09:00:00+05:30"


class RegStore:
    def __init__(self):
        self.alerts_, self.lic, self.staff = [], {}, {}

    def init_schema(self): ...
    def get_staff(self, u):
        return self.staff.get(u)

    def add_staff(self, r: StaffRecord):
        self.staff[r.username] = r

    def add_alert(self, a: NewAlert):
        al = Alert(alert_id="A1", **a.model_dump())
        self.alerts_.append(al)
        return al

    def alerts(self, gtin=None, lot=None, state=None):
        return self.alerts_

    def set_licence(self, lic):
        self.lic[lic.org_id] = lic

    def licences(self, org_ids=None):
        return list(self.lic.values())


def test_regulator_issues_alerts_and_licences_from_the_portal(make_node):
    n = make_node("regulator", store=RegStore())
    assert n.client.post("/api/alerts", json={}).status_code == 401
    n.login()
    r = n.client.post("/api/alerts", json={"kind": "nsq", "gtin": "08901003000111", "lot": "K/26/0001",
                                           "manufacturer_org": "kesar", "reason": "fails assay", "states": ["DL"], "at": AT})  # fmt: skip
    assert r.status_code == 201 and r.json()["states"] == ["DL"]
    assert len(n.client.get("/api/alerts").json()["alerts"]) == 1
    bad = n.client.post("/api/licences", json={"org_id": "x", "licence_no": "1", "licence_type": "retail",
                                              "valid_from": "2026-01-02", "valid_to": "2026-01-01"})  # fmt: skip
    assert bad.status_code == 422 and bad.json()["code"] == "bad_dates"


def test_consumer_report_text_is_redacted_before_it_is_stored(make_node):
    n = make_node("consumer")
    r = n.client.post("/api/report", json={"text": "Bought at Sharma Medicos, call me on 9876543210 or a@b.in",
                                          "city": "Delhi", "gtin": "08901003000111", "serial": "KS000000001"})  # fmt: skip
    assert r.status_code == 201 and sorted(r.json()["removed"]) == ["email", "phone"]
    stored = n.client.app.state.documents.get(r.json()["doc_id"])
    assert "9876543210" not in stored["text"] and "a@b.in" not in stored["text"]
    assert len(n.rw.reports()) == 1


def test_a_report_with_nothing_but_contact_details_is_refused(make_node):
    n = make_node("consumer")
    r = n.client.post("/api/report", json={"text": "9876543210 9876543211", "city": "Delhi"})
    assert r.status_code == 422 and r.json()["code"] == "too_short"


def test_pharma_recall_changes_the_batch_status_the_share_api_shows(make_node):
    n = make_node("pharma")
    n.login()
    g = n.client.post(
        "/api/products",
        json={"brand": "B", "generic": "g", "strength": "5 mg", "form": "tablet", "pack_size": 10},
    ).json()["gtin"]
    lot = n.client.post(
        "/api/batches", json={"gtin": g, "mfg_date": "2026-10-05", "expiry_date": "2028-09-30", "quantity": 5}
    ).json()["lot"]
    assert n.signed_get(f"/share/v1/batches?gtin={g}").json()["batches"][0]["status"] == "released"
    assert (
        n.client.post(
            "/api/recalls", json={"gtin": g, "lot": lot, "reason": "failed assay", "at": AT}
        ).status_code
        == 201
    )
    assert n.signed_get(f"/share/v1/batches?gtin={g}").json()["batches"][0]["status"] == "recalled"
    assert n.client.post(f"/api/batches/{lot}/packs", json={"count": 1}).status_code == 409  # recalled batch
