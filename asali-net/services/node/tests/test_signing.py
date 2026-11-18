from pathlib import Path

import pytest
from asali_node.auth.signing import (
    ShareAuthError,
    load_or_create_keys,
    public_key_b64,
    sign_request,
    verify_request,
)
from asali_node.main import create_app
from asali_node.settings import Settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

NOW = 1_800_000_000
PATH = "/share/v1/units/08901001000124/TPM9S346Q37?x=1"


@pytest.fixture
def key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def lookup_for(key: Ed25519PrivateKey, org: str = "dist-north"):
    pub = public_key_b64(key)
    return lambda org_id: pub if org_id == org else None


def test_round_trip(key):
    headers = sign_request(key, "dist-north", "GET", PATH, NOW)
    assert verify_request(headers, "GET", PATH, NOW + 5, lookup_for(key)) == "dist-north"


def test_headers_are_case_insensitive(key):
    headers = {k.lower(): v for k, v in sign_request(key, "dist-north", "GET", PATH, NOW).items()}
    assert verify_request(headers, "GET", PATH, NOW, lookup_for(key)) == "dist-north"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"path": "/share/v1/units/08901001000124/TPD25VT4F5H?x=1"}, "bad_signature"),
        ({"method": "POST"}, "bad_signature"),
        ({"now": NOW + 121}, "clock_skew"),
        ({"now": NOW - 121}, "clock_skew"),
    ],
)
def test_tampering_and_skew_are_refused(key, change, reason):
    headers = sign_request(key, "dist-north", "GET", PATH, NOW)
    args = {"method": "GET", "path": PATH, "now": NOW, **change}
    with pytest.raises(ShareAuthError) as e:
        verify_request(headers, args["method"], args["path"], args["now"], lookup_for(key))
    assert e.value.reason == reason


def test_unknown_org_and_wrong_key(key):
    headers = sign_request(key, "dist-north", "GET", PATH, NOW)
    with pytest.raises(ShareAuthError) as e:
        verify_request(headers, "GET", PATH, NOW, lambda _: None)
    assert e.value.reason == "unknown_org"
    with pytest.raises(ShareAuthError) as e:
        verify_request(headers, "GET", PATH, NOW, lookup_for(Ed25519PrivateKey.generate()))
    assert e.value.reason == "bad_signature"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Asali-Org": "dist-north"},
        {"X-Asali-Org": "dist-north", "X-Asali-Time": "soon", "X-Asali-Signature": "x"},
    ],
)
def test_missing_or_malformed_headers(key, headers):
    with pytest.raises(ShareAuthError):
        verify_request(headers, "GET", PATH, NOW, lookup_for(key))


def test_keys_are_created_once_and_reloaded(tmp_path: Path):
    k1 = load_or_create_keys(tmp_path)
    k2 = load_or_create_keys(tmp_path)
    assert public_key_b64(k1) == public_key_b64(k2)
    assert (tmp_path / "keys" / "node_ed25519.pem").exists()


def test_guard_protects_share_routes_but_not_health(settings: Settings, key):
    app = create_app(settings)
    app.state.key_lookup = lookup_for(key)
    app.state.clock = lambda: NOW
    client = TestClient(app)
    assert client.get("/share/v1/health").status_code == 200
    r = client.get("/share/v1/org")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "unknown_org"
    signed = sign_request(key, "dist-north", "GET", "/share/v1/org", NOW)
    assert client.get("/share/v1/org", headers=signed).status_code == 200
    stale = sign_request(key, "dist-north", "GET", "/share/v1/org", NOW - 500)
    assert client.get("/share/v1/org", headers=stale).json()["code"] == "clock_skew"


def test_guard_does_not_touch_portal_routes(settings: Settings):
    client = TestClient(create_app(settings))
    assert client.get("/api/config").status_code == 200
