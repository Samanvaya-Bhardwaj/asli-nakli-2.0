import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from addressing import Addressing, staff_password

ROWS = [
    {"org_id": "shop-delhi", "base_url": "https://192.168.1.40:8201", "org_type": "shop"},
    {"org_id": "tarang", "base_url": "https://192.168.1.20:8301", "org_type": "pharma"},
]


def fake(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/directory/v1/orgs"
    return httpx.Response(200, json=ROWS)


def test_addresses_come_from_the_directory_not_from_the_scripts():
    a = Addressing("https://192.168.1.11:8400", transport=httpx.MockTransport(fake))
    assert a.url("tarang") == "https://192.168.1.20:8301"
    assert a.url("shop-delhi") == "https://192.168.1.40:8201"


def test_an_organisation_the_directory_does_not_list_is_named_in_the_error():
    a = Addressing("https://192.168.1.11:8400", transport=httpx.MockTransport(fake))
    with pytest.raises(RuntimeError, match="dist-west"):
        a.url("dist-west")


def test_a_consumer_portal_is_found_by_city():
    rows = [
        *ROWS,
        {"org_id": "consumer-delhi", "base_url": "https://x:8402", "org_type": "consumer", "city": "Delhi"},
    ]
    a = Addressing("https://d:8400", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=rows)))
    assert a.consumer("Delhi") == "https://x:8402"


def test_the_password_is_taken_from_the_flag_then_the_environment_then_the_simulation_file(
    tmp_path, monkeypatch
):
    f = tmp_path / "secrets.json"
    f.write_text('{"staff_password": "from-file"}')
    monkeypatch.delenv("ASALI_STAFF_PASSWORD", raising=False)
    assert staff_password(None, f) == "from-file"
    monkeypatch.setenv("ASALI_STAFF_PASSWORD", "from-env")
    assert staff_password(None, f) == "from-env"
    assert staff_password("from-flag", f) == "from-flag"
