"""Live answers from the running network must fit the shapes the portal's TypeScript types are generated from."""

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infra" / "out" / "SIM"
sys.path.insert(0, str(ROOT / "services" / "node"))
from asali_node import contract as c  # noqa: E402

pytestmark = pytest.mark.network


@pytest.mark.parametrize("name", ["S1", "S3", "S5", "S6", "S7"])
def test_a_finished_check_fits_the_contract(name, consumer, scenarios):
    body = consumer.post("/api/check", json={"raw": scenarios[name]["raw"], "city": "Delhi"}).json()
    c.CheckDone.model_validate(body)


def test_a_misread_code_reply_fits_the_contract(consumer, scenarios):
    body = consumer.post("/api/check", json={"raw": scenarios["S9"]["raw"], "city": "Delhi"}).json()
    c.CheckNeedsConfirmation.model_validate(body)


def test_config_network_and_parties_fit_the_contract(consumer):
    c.Config.model_validate(consumer.get("/api/config").json())
    c.Network.model_validate(consumer.get("/api/network").json())
    c.Parties.model_validate(consumer.get("/api/parties").json())


def test_a_shops_config_and_me_fit_the_contract():
    password = json.loads((OUT / "secrets.json").read_text())["staff_password"]
    with httpx.Client(base_url="http://127.0.0.1:8201", timeout=30) as shop:
        assert shop.post("/api/login", json={"username": "staff", "password": password}).status_code == 200
        cfg = c.Config.model_validate(shop.get("/api/config").json())
        assert cfg.shop is not None
        c.Me.model_validate(shop.get("/api/me").json())
