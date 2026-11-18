"""Signed GET requests to other organisations' share APIs (PLAN.md section 8.3).

Every failure becomes a SourceUnavailable with a reason, so a result can say who did not answer and why.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from asali_node.auth.signing import sign_request
from asali_node.network.breaker import Breaker

TIMEOUT = httpx.Timeout(2.0)
Call = tuple[str, str, dict[str, Any] | None]


class SourceUnavailable(Exception):
    """reason: timeout | unreachable | skipped | budget | unknown_org | bad_response | http_<status>"""

    def __init__(self, org_id: str, reason: str) -> None:
        super().__init__(f"{org_id}: {reason}")
        self.org_id, self.reason = org_id, reason


class ShareClient:
    def __init__(
        self,
        org_id: str,
        key: Ed25519PrivateKey,
        http: httpx.AsyncClient,
        base_url_for: Callable[[str], str | None],
        clock: Callable[[], float] = time.time,
        breaker: Breaker | None = None,
        on_unknown: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.org_id, self.key, self.http = org_id, key, http
        self.base_url_for, self.clock = base_url_for, clock
        self.breaker = breaker or Breaker()
        self.on_unknown = on_unknown

    async def get(self, org_id: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.breaker.is_open(org_id, self.clock()):
            raise SourceUnavailable(org_id, "skipped")
        base = self.base_url_for(org_id)
        if base is None and self.on_unknown is not None:
            await self.on_unknown()
            base = self.base_url_for(org_id)
        if base is None:
            raise SourceUnavailable(org_id, "unknown_org")
        reason = "unreachable"
        for _attempt in range(2):
            request = self.http.build_request("GET", base.rstrip("/") + path, params=params, timeout=TIMEOUT)
            signed_path = request.url.raw_path.decode("ascii")
            request.headers.update(sign_request(self.key, self.org_id, "GET", signed_path, int(self.clock())))
            try:
                response = await self.http.send(request)
            except httpx.TimeoutException:
                reason = "timeout"
                continue
            except httpx.TransportError:
                reason = "unreachable"
                continue
            self.breaker.record_success(org_id)
            if response.status_code >= 400:
                raise SourceUnavailable(org_id, f"http_{response.status_code}")
            try:
                body: dict[str, Any] = response.json()
            except ValueError:
                raise SourceUnavailable(org_id, "bad_response") from None
            return body
        self.breaker.record_failure(org_id, self.clock())
        raise SourceUnavailable(org_id, reason)

    async def gather(self, calls: list[Call], budget_s: float) -> list[dict[str, Any] | SourceUnavailable]:
        """Run calls in parallel; whatever has not answered when the budget runs out is marked 'budget'."""
        tasks = [asyncio.create_task(self.get(org, path, params)) for org, path, params in calls]
        if tasks:
            await asyncio.wait(tasks, timeout=budget_s)
        results: list[dict[str, Any] | SourceUnavailable] = []
        for (org, _, _), task in zip(calls, tasks, strict=True):
            if not task.done():
                task.cancel()
                results.append(SourceUnavailable(org, "budget"))
            elif isinstance(task.exception(), SourceUnavailable):
                results.append(task.exception())  # type: ignore[arg-type]
            elif task.exception() is not None:
                results.append(SourceUnavailable(org, type(task.exception()).__name__))
            else:
                results.append(task.result())
        return results
