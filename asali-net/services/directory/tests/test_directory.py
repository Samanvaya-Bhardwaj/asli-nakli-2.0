import base64
import sqlite3
from pathlib import Path

import pytest
from asali_directory.main import create_app
from asali_directory.settings import Settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

JOIN = "join-secret"
ADMIN = "admin-secret"


class Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


def pub_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def signed(key: Ed25519PrivateKey, org: str, method: str, path: str, t: int) -> dict[str, str]:
    msg = f"{method}\n{path}\n{t}\n{org}".encode()
    return {
        "X-Asali-Org": org,
        "X-Asali-Time": str(t),
        "X-Asali-Signature": base64.b64encode(key.sign(msg)).decode(),
    }


def org_body(org_id: str, key: Ed25519PrivateKey, **over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "org_id": org_id,
        "org_type": "pharma",
        "name": "Tarang Pharma",
        "city": "Baddi",
        "state": "HP",
        "issuer_code": "TP",
        "gs1_prefix": "8901001",
        "base_url": "https://10.0.0.2:8301",
        "public_key": pub_b64(key),
        "host_name": "PC-B",
    }
    body.update(over)
    return body


@pytest.fixture
def env(tmp_path: Path):
    clock = Clock()
    settings = Settings(join_token=JOIN, admin_token=ADMIN, data_dir=tmp_path)
    client = TestClient(create_app(settings, clock=clock))
    return client, clock, tmp_path


def register(client: TestClient, body: dict[str, object], token: str = JOIN, **headers: str):
    return client.post("/directory/v1/register", json=body, headers={"X-Join-Token": token, **headers})


def test_health(env):
    client, _, _ = env
    assert client.get("/directory/v1/health").json() == {"status": "ok"}


def test_register_needs_the_join_token(env):
    client, _, _ = env
    key = Ed25519PrivateKey.generate()
    r = register(client, org_body("tarang", key), token="wrong")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["status"] == 401


def test_register_creates_then_updates_with_same_key(env):
    client, _, _ = env
    key = Ed25519PrivateKey.generate()
    assert register(client, org_body("tarang", key)).status_code == 201
    r = register(client, org_body("tarang", key, base_url="https://10.0.0.9:8301"))
    assert r.status_code == 200
    assert client.get("/directory/v1/orgs/tarang").json()["base_url"] == "https://10.0.0.9:8301"


def test_same_org_with_different_key_is_refused_unless_admin(env):
    client, _, _ = env
    register(client, org_body("tarang", Ed25519PrivateKey.generate()))
    other = org_body("tarang", Ed25519PrivateKey.generate())
    assert register(client, other).status_code == 409
    assert register(client, other, **{"X-Admin-Token": ADMIN}).status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        {"org_id": "Bad Id"},
        {"org_type": "hospital"},
        {"public_key": "not-a-key"},
        {"issuer_code": "TU"},
        {"base_url": "ftp://x"},
    ],
)
def test_invalid_registrations_are_rejected(env, bad):
    client, _, _ = env
    body = org_body("tarang", Ed25519PrivateKey.generate())
    body.update(bad)
    r = register(client, body)
    assert r.status_code == 422


def test_heartbeat_with_valid_signature_marks_online(env):
    client, clock, _ = env
    key = Ed25519PrivateKey.generate()
    register(client, org_body("tarang", key))
    clock.now += 200
    assert client.get("/directory/v1/orgs/tarang").json()["online"] is False
    t = int(clock.now)
    r = client.post(
        "/directory/v1/heartbeat", headers=signed(key, "tarang", "POST", "/directory/v1/heartbeat", t)
    )
    assert r.status_code == 200
    assert client.get("/directory/v1/orgs/tarang").json()["online"] is True


def test_heartbeat_with_bad_signature_or_skew_is_refused(env):
    client, clock, _ = env
    key = Ed25519PrivateKey.generate()
    register(client, org_body("tarang", key))
    t = int(clock.now)
    wrong_key = signed(Ed25519PrivateKey.generate(), "tarang", "POST", "/directory/v1/heartbeat", t)
    r = client.post("/directory/v1/heartbeat", headers=wrong_key)
    assert (r.status_code, r.json()["code"]) == (401, "bad_signature")
    skewed = signed(key, "tarang", "POST", "/directory/v1/heartbeat", t - 121)
    r = client.post("/directory/v1/heartbeat", headers=skewed)
    assert (r.status_code, r.json()["code"]) == (401, "clock_skew")
    unknown = signed(key, "nobody", "POST", "/directory/v1/heartbeat", t)
    r = client.post("/directory/v1/heartbeat", headers=unknown)
    assert (r.status_code, r.json()["code"]) == (401, "unknown_org")


def test_online_window_is_90_seconds(env):
    client, clock, _ = env
    register(client, org_body("tarang", Ed25519PrivateKey.generate()))
    clock.now += 89
    assert client.get("/directory/v1/orgs/tarang").json()["online"] is True
    clock.now += 2
    assert client.get("/directory/v1/orgs/tarang").json()["online"] is False


def test_list_filters_by_type_and_state(env):
    client, _, _ = env
    register(client, org_body("tarang", Ed25519PrivateKey.generate()))
    shop = org_body(
        "shop-delhi", Ed25519PrivateKey.generate(), org_type="shop", name="Sharma Medicos", city="Delhi",
        state="DL", issuer_code=None, gs1_prefix=None,
    )  # fmt: skip
    register(client, shop)
    assert [o["org_id"] for o in client.get("/directory/v1/orgs").json()] == ["shop-delhi", "tarang"]
    assert [o["org_id"] for o in client.get("/directory/v1/orgs?type=shop").json()] == ["shop-delhi"]
    assert [o["org_id"] for o in client.get("/directory/v1/orgs?state=HP").json()] == ["tarang"]


def test_issuer_and_longest_prefix_lookup(env):
    client, _, _ = env
    register(client, org_body("tarang", Ed25519PrivateKey.generate()))
    register(
        client,
        org_body(
            "medivra", Ed25519PrivateKey.generate(), issuer_code="MV", gs1_prefix="89010012", name="Medivra"
        ),
    )
    assert client.get("/directory/v1/issuers/TP").json()["org_id"] == "tarang"
    assert client.get("/directory/v1/issuers/ZZ").status_code == 404
    assert client.get("/directory/v1/prefixes/08901001200009").json()["org_id"] == "medivra"
    assert client.get("/directory/v1/prefixes/08901001000124").json()["org_id"] == "tarang"
    assert client.get("/directory/v1/prefixes/08909999000000").status_code == 404


def test_unknown_org_is_404_problem(env):
    client, _, _ = env
    r = client.get("/directory/v1/orgs/nobody")
    assert r.status_code == 404
    assert r.json()["title"]


def test_directory_holds_no_table_but_orgs(env):
    client, _, data_dir = env
    register(client, org_body("tarang", Ed25519PrivateKey.generate()))
    with sqlite3.connect(data_dir / "directory.sqlite") as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert tables == ["orgs"]
