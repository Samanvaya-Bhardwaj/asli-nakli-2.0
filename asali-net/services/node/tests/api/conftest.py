"""Nodes for API tests: real SQLite stores, fake peers. The stores themselves are covered by the contract suite."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from asali_node.auth.signing import public_key_b64, sign_request
from asali_node.main import create_app
from asali_node.network.client import SourceUnavailable
from asali_node.settings import Settings
from asali_node.stores.registry import open_store
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

NOW = 1_800_000_000
KEY = Ed25519PrivateKey.generate()
PASSWORD = "correct horse"
ORGS = [
    {"org_id": "kesar", "org_type": "pharma", "name": "Kesar Biologics", "city": "Pune", "state": "MH",
     "host_name": "PC-B", "issuer_code": "KS", "online": True},
    {"org_id": "dist-south", "org_type": "distributor", "name": "Dakshin Pharma Agencies", "city": "Bengaluru",
     "state": "KA", "host_name": "PC-C", "issuer_code": None, "online": True},
    {"org_id": "shop-delhi", "org_type": "shop", "name": "Sharma Medicos", "city": "Delhi", "state": "DL",
     "host_name": "PC-D", "issuer_code": None, "online": True},
    {"org_id": "regulator", "org_type": "regulator", "name": "Drug Control", "city": "Delhi", "state": "DL",
     "host_name": "PC-A", "issuer_code": None, "online": True},
]  # fmt: skip
SQLITE_STORE = {
    "pharma": "kesar",
    "distributor": "dist-south",
    "shop": "shop-delhi",
    "consumer": "consumer-delhi",
}


class FakeDirectory:
    def __init__(self) -> None:
        self.orgs = ORGS

    def known(self) -> list[dict[str, Any]]:
        return self.orgs


class FakeShare:
    """Canned answers by (org, path). An answer that is a SourceUnavailable is raised."""

    def __init__(self) -> None:
        self.answers: dict[tuple[str, str], Any] = {}
        self.asked: list[tuple[str, str, Any]] = []

    async def get(self, org: str, path: str, params: Any = None) -> dict[str, Any]:
        self.asked.append((org, path, params))
        a = self.answers.get((org, path), SourceUnavailable(org, "unreachable"))
        if isinstance(a, Exception):
            raise a
        return a  # type: ignore[no-any-return]

    async def gather(self, calls: list[Any], budget_s: float) -> list[Any]:
        out: list[Any] = []
        for org, path, params in calls:
            try:
                out.append(await self.get(org, path, params))
            except SourceUnavailable as e:
                out.append(e)
        return out


class Node:
    def __init__(self, client: TestClient, settings: Settings, rw: Any, ro: Any, share: FakeShare) -> None:
        self.client, self.settings, self.rw, self.ro, self.share = client, settings, rw, ro, share

    def login(self, username: str = "asha") -> None:
        r = self.client.post("/api/login", json={"username": username, "password": PASSWORD})
        assert r.status_code == 200, r.text

    def signed_get(self, path: str, caller: str = "dist-south") -> Any:
        return self.client.get(path, headers=sign_request(KEY, caller, "GET", path, NOW))


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")


@pytest.fixture
def make_node(tmp_path: Path) -> Callable[..., Node]:
    def build(org_type: str, org_id: str | None = None, store: Any = None, **extra: Any) -> Node:
        info = next((o for o in ORGS if o["org_type"] == org_type), None) or {
            "org_id": f"consumer-{org_type}",
            "name": "Consumer",
            "city": "Delhi",
            "state": "DL",
            "issuer_code": None,
        }
        org_id = org_id or info["org_id"]
        data = tmp_path / org_id
        data.mkdir(exist_ok=True)
        s = Settings(
            org_id=org_id, org_type=org_type, org_name=info["name"], org_city=info["city"], org_state=info["state"],
            issuer_code=info["issuer_code"], gs1_prefix="8901003" if org_type == "pharma" else None,
            engine="sqlite", sqlite_path=data / "own.sqlite", directory_url="https://dir", join_token="t",
            public_base_url="https://me", host_name="PC-TEST", asali_mode="simulation", data_dir=data,
            staff_seed_json='[{"username": "asha", "password": "%s", "role": "admin", "display_name": "Asha"}]' % PASSWORD,
            served_states='["KA"]',
        )  # fmt: skip
        rw = store or open_store(SQLITE_STORE.get(org_type, org_id), str(s.sqlite_path), "rw", s.org_city)
        rw.init_schema()
        ro = (
            open_store(SQLITE_STORE.get(org_type, org_id), str(s.sqlite_path), "ro", s.org_city)
            if store is None
            else store
        )
        app = create_app(s, rw, ro)
        share = FakeShare()
        app.state.share, app.state.directory = share, FakeDirectory()
        app.state.key_lookup = lambda org: public_key_b64(KEY) if org in {o["org_id"] for o in ORGS} else None
        app.state.clock = lambda: NOW
        app.state.issuer_codes = lambda: {"KS", "TP", "MV"}
        return Node(TestClient(app), s, rw, ro, share)

    return build


def _signed(self: Node, method: str, path: str, caller: str = "dist-south") -> Any:
    return self.client.request(method, path, headers=sign_request(KEY, caller, method, path, NOW))


Node.signed = _signed  # type: ignore[attr-defined]
