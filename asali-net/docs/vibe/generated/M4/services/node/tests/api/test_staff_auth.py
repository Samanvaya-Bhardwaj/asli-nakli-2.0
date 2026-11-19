def test_login_sets_an_httponly_lax_cookie(make_node):
    n = make_node("pharma")
    r = n.client.post("/api/login", json={"username": "asha", "password": "correct horse"})
    assert r.status_code == 200
    assert r.json()["org_id"] == "kesar" and r.json()["role"] == "admin"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert n.client.get("/api/me").json()["username"] == "asha"


def test_wrong_password_is_a_problem_json_401(make_node):
    n = make_node("pharma")
    r = n.client.post("/api/login", json={"username": "asha", "password": "nope"})
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["detail"] == "Wrong username or password."
    assert n.client.post("/api/login", json={"username": "ghost", "password": "x"}).status_code == 401


def test_write_routes_need_a_session(make_node):
    n = make_node("pharma")
    assert n.client.post("/api/products", json={}).status_code == 401
    assert n.client.get("/api/activity").status_code == 401
    assert n.client.post("/api/scan/sessions", json={"kind": "dispatch"}).status_code == 401


def test_logout_ends_the_session(make_node):
    n = make_node("pharma")
    n.login()
    assert n.client.post("/api/logout").status_code == 200
    assert n.client.get("/api/me").status_code == 401


def test_seeding_twice_does_not_duplicate_staff(make_node):
    n = make_node("pharma")
    from asali_node.auth.staff import seed_staff

    assert seed_staff(n.rw, n.settings.staff_seed_json) == 0


def test_consumer_report_needs_no_session(make_node):
    n = make_node("consumer")
    r = n.client.post(
        "/api/report", json={"text": "The tablets smell strange and look different.", "city": "Delhi"}
    )
    assert r.status_code == 201
