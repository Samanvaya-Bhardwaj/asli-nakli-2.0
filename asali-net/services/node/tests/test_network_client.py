import asyncio

import httpx
import pytest
from asali_node.auth.signing import public_key_b64, verify_request
from asali_node.main import create_app
from asali_node.network.client import ShareClient, SourceUnavailable
from asali_node.settings import Settings
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

pytestmark = pytest.mark.anyio

BASES = {"dist-north": "https://10.0.0.3:8101", "tarang": "https://10.0.0.2:8301"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


def make(handler, clock: Clock | None = None, key: Ed25519PrivateKey | None = None):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ShareClient(
        "shop-delhi", key or Ed25519PrivateKey.generate(), http, BASES.get, clock=clock or Clock()
    )
    return client, http


async def test_get_returns_json_and_signs_path_with_query():
    key = Ed25519PrivateKey.generate()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client, http = make(handler, key=key)
    async with http:
        assert await client.get("dist-north", "/share/v1/units/exists", {"serials": "A,B"}) == {"ok": True}
    req = seen[0]
    assert str(req.url).startswith("https://10.0.0.3:8101/share/v1/units/exists?")
    pub = public_key_b64(key)
    caller = verify_request(req.headers, "GET", req.url.raw_path.decode(), 1_800_000_000, lambda _: pub)
    assert caller == "shop-delhi"


async def test_signature_is_accepted_by_a_real_node_guard(settings: Settings):
    key = Ed25519PrivateKey.generate()
    node = create_app(settings)
    node.state.key_lookup = lambda org: public_key_b64(key) if org == "shop-delhi" else None
    node.state.clock = Clock()
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=node))
    client = ShareClient("shop-delhi", key, http, lambda _: "https://10.0.0.4:8202", clock=Clock())
    async with http:
        with pytest.raises(SourceUnavailable) as e:
            await client.get("shop-mumbai", "/share/v1/org", {"serials": "A,B", "q": "x y"})
    assert (
        e.value.reason == "http_404"
    )  # 404, not 401: the guard accepted the signature; the route arrives in M4


async def test_timeout_is_retried_once_then_reported():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow", request=request)

    client, http = make(handler)
    async with http:
        with pytest.raises(SourceUnavailable) as e:
            await client.get("dist-north", "/share/v1/org")
    assert (e.value.org_id, e.value.reason, attempts) == ("dist-north", "timeout", 2)


async def test_refused_connection_is_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client, http = make(handler)
    async with http:
        with pytest.raises(SourceUnavailable) as e:
            await client.get("dist-north", "/share/v1/org")
    assert e.value.reason == "unreachable"


async def test_unknown_org_is_reported_without_a_request():
    client, http = make(lambda r: httpx.Response(200, json={}))
    async with http:
        with pytest.raises(SourceUnavailable) as e:
            await client.get("nobody", "/share/v1/org")
    assert e.value.reason == "unknown_org"


async def test_breaker_skips_a_node_for_30_seconds_after_two_failures():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("refused", request=request)

    clock = Clock()
    client, http = make(handler, clock=clock)
    async with http:
        for _ in range(2):
            with pytest.raises(SourceUnavailable):
                await client.get("dist-north", "/share/v1/org")
        before = calls
        with pytest.raises(SourceUnavailable) as e:
            await client.get("dist-north", "/share/v1/org")
        assert e.value.reason == "skipped"
        assert calls == before
        clock.now += 31
        with pytest.raises(SourceUnavailable) as e:
            await client.get("dist-north", "/share/v1/org")
        assert e.value.reason == "unreachable"
        assert calls > before


async def test_http_errors_from_a_live_node_do_not_trip_the_breaker():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"title": "Not found"})

    client, http = make(handler)
    async with http:
        for _ in range(3):
            with pytest.raises(SourceUnavailable) as e:
                await client.get("dist-north", "/share/v1/org")
            assert e.value.reason == "http_404"


async def test_gather_returns_within_budget_and_marks_late_answers():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "10.0.0.2":
            await asyncio.sleep(1.0)
        return httpx.Response(200, json={"host": request.url.host})

    client, http = make(handler)
    async with http:
        loop = asyncio.get_running_loop()
        start = loop.time()
        results = await client.gather(
            [
                ("dist-north", "/share/v1/org", None),
                ("tarang", "/share/v1/org", None),
                ("nobody", "/x", None),
            ],
            budget_s=0.2,
        )
        elapsed = loop.time() - start
    assert elapsed < 0.6
    assert results[0] == {"host": "10.0.0.3"}
    assert isinstance(results[1], SourceUnavailable) and results[1].reason == "budget"
    assert isinstance(results[2], SourceUnavailable) and results[2].reason == "unknown_org"
