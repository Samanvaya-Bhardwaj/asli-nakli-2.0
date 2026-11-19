"""Tests against the running simulation network (infra/scripts/run_local_network.py + seed + scenarios).

    uv run pytest tests/network --simulation-up

Without the option these tests are skipped with that reason. They need the network to be up and seeded.
"""

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infra" / "out" / "SIM"
sys.path.insert(0, str(ROOT / "infra" / "scripts"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--simulation-up", action="store_true", help="run tests that need the simulation network")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--simulation-up", default=False):
        return
    skip = pytest.mark.skip(reason="needs the simulation network: start it, seed it, then pass --simulation-up")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def scenarios() -> dict:
    return json.loads((OUT / "scenarios.json").read_text())


@pytest.fixture(scope="session")
def expected() -> dict:
    return json.loads((ROOT / "seed" / "expected.json").read_text())


@pytest.fixture(scope="session")
def consumer() -> httpx.Client:
    return httpx.Client(base_url="http://127.0.0.1:8402", timeout=30)
