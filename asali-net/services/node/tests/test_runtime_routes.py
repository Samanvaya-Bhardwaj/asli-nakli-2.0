import pytest
from asali_node.auth.signing import public_key_b64, sign_request
from asali_node.main import create_app
from asali_node.network.client import SourceUnavailable
from asali_node.settings import Settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

NOW = 1_800_000_000


def signed_client(settings: Settings, key: Ed25519PrivateKey) -> TestClient:
    app = create_app(settings)
    app.state.key_lookup = lambda org: public_key_b64(key) if org == "dist-north" else None
    app.state.clock = lambda: NOW
    return TestClient(app)


def test_share_org_describes_the_node_and_who_served_it(settings: Settings):
    key = Ed25519PrivateKey.generate()
    client = signed_client(settings, key)
    r = client.get("/share/v1/org", headers=sign_request(key, "dist-north", "GET", "/share/v1/org", NOW))
    assert r.status_code == 200
    org = r.json()
    assert org["org_id"] == "shop-mumbai"
    assert org["engine"] == "sqlite"
    assert org["vault"] == "meilisearch"
    assert org["served_by"]["host_name"] == "PC-D"
    assert org["served_by"]["org_id"] == "shop-mumbai"
    assert "secret" not in str(org)


class FakeShare:
    def __init__(self, result):
        self.result = result

    async def get(self, org_id, path, params=None):
        if isinstance(self.result, Exception):
            raise self.result
        return {"asked": org_id, "path": path, **self.result}


def test_debug_ask_works_only_in_simulation(settings: Settings):
    app = create_app(settings)
    app.state.share = FakeShare({"ok": True})
    r = TestClient(app).get("/api/debug/ask", params={"org": "tarang", "path": "/share/v1/org"})
    assert r.status_code == 200
    assert r.json() == {"asked": "tarang", "path": "/share/v1/org", "ok": True}

    network = create_app(Settings(**{**settings.model_dump(), "asali_mode": "network"}))
    network.state.share = FakeShare({"ok": True})
    assert (
        TestClient(network).get("/api/debug/ask", params={"org": "x", "path": "/share/v1/org"}).status_code
        == 404
    )


def test_debug_ask_reports_unavailable_sources_as_problem(settings: Settings):
    app = create_app(settings)
    app.state.share = FakeShare(SourceUnavailable("tarang", "timeout"))
    r = TestClient(app).get("/api/debug/ask", params={"org": "tarang", "path": "/share/v1/org"})
    assert r.status_code == 502
    assert r.json()["code"] == "timeout"


def test_debug_ask_only_reaches_share_paths(settings: Settings):
    app = create_app(settings)
    app.state.share = FakeShare({})
    r = TestClient(app).get("/api/debug/ask", params={"org": "tarang", "path": "/api/config"})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_guard_refreshes_directory_once_on_unknown_caller(settings: Settings):
    import httpx

    key = Ed25519PrivateKey.generate()
    known: dict[str, str] = {}
    refreshes = 0

    async def refresh() -> None:
        nonlocal refreshes
        refreshes += 1
        known["dist-north"] = public_key_b64(key)

    app = create_app(settings)
    app.state.key_lookup = known.get
    app.state.refresh_directory = refresh
    app.state.clock = lambda: NOW
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://n") as http:
        r = await http.get(
            "/share/v1/org", headers=sign_request(key, "dist-north", "GET", "/share/v1/org", NOW)
        )
    assert r.status_code == 200
    assert refreshes == 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
