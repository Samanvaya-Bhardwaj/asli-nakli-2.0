"""A small client for one organisation's portal API, used by the seed and the scenario scripts."""

import random
from datetime import datetime, timedelta
from typing import Any

import httpx

SIM_START = datetime.fromisoformat("2026-10-01T09:00:00+05:30")


class Portal:
    def __init__(self, org_id: str, base_url: str, password: str, verify: Any = True) -> None:
        self.org_id, self.base = org_id, base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=30, verify=verify)
        r = self.http.post("/api/login", json={"username": "staff", "password": password})
        if r.status_code != 200:
            raise RuntimeError(f"{org_id}: sign-in failed ({r.status_code} {r.text})")

    def call(self, method: str, path: str, ok: tuple[int, ...] = (200, 201), **kw: Any) -> Any:
        r = self.http.request(method, path, **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"{self.org_id} {method} {path}: {r.status_code} {r.text}")
        return r.json()

    def scan_session(self, kind: str, codes: list[tuple[str, str]], rng: random.Random, misread_rate: float,
                     finish: dict[str, Any], **start: Any) -> dict[str, Any]:  # fmt: skip
        """Type each code in as a person would, sometimes with a slip, and finish the session."""
        sid = self.call("POST", "/api/scan/sessions", json={"kind": kind, **start})["session_id"]
        slips = 0
        for gtin, serial in codes:
            raw, slipped = f"(01){gtin}(21){serial}", False
            if rng.random() < misread_rate:
                i = rng.randrange(2, 9)
                raw, slipped = f"(01){gtin}(21){serial[:i]}{serial[i + 1]}{serial[i]}{serial[i + 2:]}", True
            row = self.call("POST", f"/api/scan/sessions/{sid}/read", json={"raw": raw, "source": "typed"})["row"]
            if row["status"] not in ("ok", "corrected"):  # a slip we could not fix: remove it and type it again
                self.call("POST", f"/api/scan/sessions/{sid}/rows/{row['row_id']}/undo")
                row = self.call("POST", f"/api/scan/sessions/{sid}/read",
                                json={"raw": f"(01){gtin}(21){serial}", "source": "typed"})["row"]  # fmt: skip
            if row["status"] not in ("ok", "corrected", "duplicate"):
                raise RuntimeError(f"{self.org_id}: could not scan {serial}: {row}")
            slips += slipped and row["status"] == "corrected"
        done = self.call("POST", f"/api/scan/sessions/{sid}/finish", json=finish)
        return {**done, "corrected": slips}


def at(hours: float) -> str:
    return (SIM_START + timedelta(hours=hours)).isoformat()
