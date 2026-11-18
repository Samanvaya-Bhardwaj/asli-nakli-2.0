import asyncio
import json
from pathlib import Path

import httpx
import pytest
from asali_directory.main import create_app as create_directory
from asali_directory.settings import Settings as DirectorySettings
from asali_node.auth.signing import load_or_create_keys, public_key_b64
from asali_node.directory_client import DirectoryClient
from asali_node.settings import Settings

pytestmark = pytest.mark.anyio


def real_directory(tmp_path: Path) -> httpx.AsyncClient:
    app = create_directory(DirectorySettings(join_token="join-secret", admin_token="a", data_dir=tmp_path / "dir"))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://10.0.0.1:8400")


def make_client(settings: Settings, http: httpx.AsyncClient) -> DirectoryClient:
    return DirectoryClient(settings, load_or_create_keys(settings.data_dir), http)


async def test_register_heartbeat_and_list_against_the_real_directory(settings: Settings, tmp_path: Path):
    async with real_directory(tmp_path) as http:
        dc = make_client(settings, http)
        me = await dc.register()
        assert me["org_id"] == "shop-mumbai"
        assert me["public_key"] == public_key_b64(load_or_create_keys(settings.data_dir))
        assert me["base_url"] == "https://10.0.0.4:8202"
        assert me["host_name"] == "PC-D"
        await dc.heartbeat()  # signed by the node, checked by the directory
        view = await dc.orgs()
        assert view.stale_since is None
        assert [o["org_id"] for o in view.orgs] == ["shop-mumbai"]
        assert dc.public_key("shop-mumbai") == me["public_key"]
        assert dc.public_key("nobody") is None
        assert dc.base_url("shop-mumbai") == "https://10.0.0.4:8202"


async def test_list_is_cached_and_used_when_directory_is_down(settings: Settings, tmp_path: Path):
    async with real_directory(tmp_path) as http:
        dc = make_client(settings, http)
        await dc.register()
        await dc.orgs()
    cache = json.loads((settings.data_dir / "directory_cache.json").read_text())
    assert [o["org_id"] for o in cache["orgs"]] == ["shop-mumbai"]

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(down), base_url="https://10.0.0.1:8400") as http:
        dc = make_client(settings, http)
        view = await dc.orgs()
        assert view.stale_since == cache["fetched_at"]
        assert [o["org_id"] for o in view.orgs] == ["shop-mumbai"]
        assert dc.public_key("shop-mumbai") is not None


async def test_directory_down_and_no_cache_gives_empty_stale_view(settings: Settings):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(down), base_url="https://10.0.0.1:8400") as http:
        view = await make_client(settings, http).orgs()
    assert view.orgs == []
    assert view.stale_since == "never"


async def test_heartbeat_loop_beats_and_refreshes_until_stopped(settings: Settings):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/orgs"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://d:8400") as http:
        dc = make_client(settings, http)
        stop = asyncio.Event()
        task = asyncio.create_task(dc.heartbeat_loop(interval=0.01, stop=stop))
        await asyncio.sleep(0.08)
        stop.set()
        await task
    beats = calls.count("POST /directory/v1/heartbeat")
    assert beats >= 3
    assert calls.count("GET /directory/v1/orgs") >= 3


async def test_heartbeat_loop_survives_directory_errors(settings: Settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"title": "down"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://d:8400") as http:
        dc = make_client(settings, http)
        stop = asyncio.Event()
        task = asyncio.create_task(dc.heartbeat_loop(interval=0.01, stop=stop))
        await asyncio.sleep(0.05)
        stop.set()
        await task  # no exception escapes


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
