"""Talks to the network directory: register at start-up, heartbeat, and keep a cached list of organisations.

The cache on disk lets a node keep working, with a "stale since" note, when the directory is down.
"""

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from asali_node.auth.signing import public_key_b64, sign_request
from asali_node.settings import Settings

log = logging.getLogger("asali.directory")


@dataclass(frozen=True)
class DirectoryView:
    orgs: list[dict[str, Any]]
    stale_since: str | None  # None when fresh; the cache time, or "never", when the directory did not answer


class DirectoryClient:
    def __init__(
        self,
        settings: Settings,
        key: Ed25519PrivateKey,
        http: httpx.AsyncClient,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.s, self.key, self.http, self.clock = settings, key, http, clock
        self.cache_path = settings.data_dir / "directory_cache.json"
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load_cache()

    def _url(self, path: str) -> str:
        return self.s.directory_url.rstrip("/") + path

    async def register(self) -> dict[str, Any]:
        body = {
            "org_id": self.s.org_id,
            "org_type": self.s.org_type,
            "name": self.s.org_name,
            "city": self.s.org_city,
            "state": self.s.org_state,
            "issuer_code": self.s.issuer_code,
            "gs1_prefix": self.s.gs1_prefix,
            "base_url": self.s.public_base_url,
            "public_key": public_key_b64(self.key),
            "host_name": self.s.host_name,
        }
        r = await self.http.post(self._url("/directory/v1/register"), json=body,
                                 headers={"X-Join-Token": self.s.join_token})  # fmt: skip
        r.raise_for_status()
        org: dict[str, Any] = r.json()
        return org

    async def heartbeat(self) -> None:
        path = "/directory/v1/heartbeat"
        headers = sign_request(self.key, self.s.org_id, "POST", path, int(self.clock()))
        r = await self.http.post(self._url(path), headers=headers)
        r.raise_for_status()

    async def orgs(self) -> DirectoryView:
        try:
            r = await self.http.get(self._url("/directory/v1/orgs"))
            r.raise_for_status()
            orgs: list[dict[str, Any]] = r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning(json.dumps({"event": "directory_unreachable", "error": type(e).__name__}))
            cached = self._read_cache()
            return DirectoryView(cached["orgs"], cached["fetched_at"] if cached["orgs"] else "never")
        self._by_id = {o["org_id"]: o for o in orgs}
        fetched_at = datetime.fromtimestamp(self.clock(), UTC).isoformat()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps({"fetched_at": fetched_at, "orgs": orgs}), encoding="utf-8")
        return DirectoryView(orgs, None)

    def public_key(self, org_id: str) -> str | None:
        org = self._by_id.get(org_id)
        return org["public_key"] if org else None

    def base_url(self, org_id: str) -> str | None:
        org = self._by_id.get(org_id)
        return org["base_url"] if org else None

    def known(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    async def heartbeat_loop(self, interval: float = 30.0, stop: asyncio.Event | None = None) -> None:
        """Heartbeat and refresh the list every interval until stop is set. Errors are logged, never raised."""
        stop = stop or asyncio.Event()
        while not stop.is_set():
            try:
                await self.heartbeat()
            except httpx.HTTPError as e:
                log.warning(json.dumps({"event": "heartbeat_failed", "error": type(e).__name__}))
            await self.orgs()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=interval)

    def _read_cache(self) -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data
        except (OSError, ValueError):
            return {"fetched_at": None, "orgs": []}

    def _load_cache(self) -> None:
        self._by_id = {o["org_id"]: o for o in self._read_cache()["orgs"]}
