"""Where each organisation's portal is, taken from the directory, so the same scripts run on one computer or four."""

import json
import os
from pathlib import Path
from typing import Any

import httpx

SIMULATION_DIRECTORY = "http://127.0.0.1:8400"


class Addressing:
    def __init__(
        self, directory_url: str, ca: str | None = None, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.directory_url = directory_url.rstrip("/")
        self.verify: Any = ca or True
        kw: dict[str, Any] = {"transport": transport} if transport else {"verify": self.verify}
        with httpx.Client(timeout=30, **kw) as http:
            r = http.get(f"{self.directory_url}/directory/v1/orgs")
            r.raise_for_status()
        self.rows: dict[str, dict[str, Any]] = {o["org_id"]: o for o in r.json()}

    def url(self, org_id: str) -> str:
        if org_id not in self.rows:
            raise RuntimeError(
                f"the directory at {self.directory_url} does not list {org_id}; is its computer running?"
            )
        return str(self.rows[org_id]["base_url"]).rstrip("/")

    def consumer(self, city: str) -> str:
        for o in self.rows.values():
            if o["org_type"] == "consumer" and o.get("city") == city:
                return str(o["base_url"]).rstrip("/")
        raise RuntimeError(f"the directory lists no consumer portal for {city}")


def staff_password(flag: str | None, secrets_file: Path) -> str:
    """Flag first, then ASALI_STAFF_PASSWORD, then the simulation's secrets file."""
    if flag:
        return flag
    if os.environ.get("ASALI_STAFF_PASSWORD"):
        return os.environ["ASALI_STAFF_PASSWORD"]
    return str(json.loads(secrets_file.read_text())["staff_password"])


def add_arguments(ap: Any) -> None:
    ap.add_argument(
        "--simulation", action="store_true", help=f"one computer: directory at {SIMULATION_DIRECTORY}"
    )
    ap.add_argument(
        "--directory-url", help="the directory of a four-computer run, e.g. https://192.168.1.11:8400"
    )
    ap.add_argument("--ca", help="the root certificate file of a four-computer run (rootCA.pem)")
    ap.add_argument("--password", help="staff password (or set ASALI_STAFF_PASSWORD)")


def from_args(args: Any) -> Addressing:
    if not (args.simulation or args.directory_url):
        raise SystemExit("give --simulation, or --directory-url (and --ca for https)")
    return Addressing(args.directory_url or SIMULATION_DIRECTORY, args.ca)
