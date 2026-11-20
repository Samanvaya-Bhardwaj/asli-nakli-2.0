import json
import logging

import pytest
from asali_node.main import create_app
from asali_node.settings import Settings
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_share_health_is_open(client: TestClient) -> None:
    r = client.get("/share/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "org_id": "shop-mumbai"}


def test_unknown_route_is_problem_json(client: TestClient) -> None:
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert {"type", "title", "status", "detail", "code"} <= body.keys()
    assert body["status"] == 404


def test_config_describes_the_portal_without_secrets(client: TestClient, settings: Settings) -> None:
    r = client.get("/api/config")
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["org_id"] == "shop-mumbai"
    assert cfg["org_type"] == "shop"
    assert cfg["name"] == "Apna Chemist"
    assert cfg["city"] == "Mumbai"
    assert cfg["mode"] == "simulation"
    assert cfg["host_name"] == "PC-D"
    assert cfg["shop"]["receipt_language"] == "mr"
    text = json.dumps(cfg)
    for secret in ("secret-pass", "meili-master-secret", "join-secret", "postgresql://", "vault:7700"):
        assert secret not in text
    assert "shop-private-salt" not in text  # the phone-hash salt stays on the node
    assert "KEY" not in text.upper().replace("_", "")
    assert "TOKEN" not in text.upper()


def test_each_request_logs_one_json_line(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="asali.access"):
        r = client.get("/share/v1/health")
    lines = [rec.getMessage() for rec in caplog.records if rec.name == "asali.access"]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["request_id"] == r.headers["x-request-id"]
    assert entry["org_id"] == "shop-mumbai"
    assert entry["status"] == 200
    assert entry["path"] == "/share/v1/health"
    assert isinstance(entry["ms"], float)


def test_incoming_request_id_is_kept(client: TestClient) -> None:
    r = client.get("/share/v1/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_settings_reject_unknown_org_type(settings: Settings) -> None:
    with pytest.raises(ValueError):
        Settings(**{**settings.model_dump(), "org_type": "hospital"})
