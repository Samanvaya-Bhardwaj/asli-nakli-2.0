"""Every share route except health needs a signed request from a registered organisation."""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from asali_node.auth.signing import ShareAuthError, verify_request
from asali_node.problems import problem_response

_OPEN = {"/share/v1/health"}
_TITLES = {
    "unknown_org": "This organisation is not in the network directory",
    "clock_skew": "The request time is too far from this node's clock; check time sync on both computers",
    "bad_signature": "The request signature does not match",
}


def install_share_guard(app: FastAPI) -> None:
    """Needs app.state.key_lookup (org id -> base64 public key or None); app.state.clock is optional."""

    @app.middleware("http")
    async def _guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if not path.startswith("/share/v1/") or path in _OPEN:
            return await call_next(request)
        clock: Callable[[], float] = getattr(request.app.state, "clock", time.time)
        lookup: Callable[[str], str | None] = getattr(request.app.state, "key_lookup", lambda _: None)
        path_with_query = path + (f"?{request.url.query}" if request.url.query else "")
        try:
            request.state.caller_org = verify_request(
                request.headers, request.method, path_with_query, clock(), lookup
            )
        except ShareAuthError as e:
            return problem_response(401, _TITLES[e.reason], e.reason)
        return await call_next(request)
