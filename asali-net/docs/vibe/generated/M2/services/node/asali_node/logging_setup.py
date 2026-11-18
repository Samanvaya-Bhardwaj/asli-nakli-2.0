"""One JSON line per request on stdout: request id, org, method, path, status, milliseconds."""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

access_log = logging.getLogger("asali.access")


def configure_logging() -> None:
    if not access_log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        access_log.addHandler(handler)
    access_log.setLevel(logging.INFO)


def install_request_logging(app: FastAPI, org_id: str) -> None:
    @app.middleware("http")
    async def _log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            entry = {
                "request_id": request_id,
                "org_id": org_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
            access_log.info(json.dumps(entry))
