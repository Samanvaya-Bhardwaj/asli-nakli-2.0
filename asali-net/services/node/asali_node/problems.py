"""Errors over HTTP as problem JSON (RFC 9457): a short machine code plus a sentence a person can act on."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_TITLES = {404: "Not found", 405: "Method not allowed", 401: "Not signed in", 403: "Not allowed"}


class Problem(Exception):
    def __init__(self, status: int, title: str, code: str, detail: str = "") -> None:
        super().__init__(title)
        self.status, self.title, self.code, self.detail = status, title, code, detail


def problem_response(status: int, title: str, code: str, detail: str = "") -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, "code": code}
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(_: Request, e: Problem) -> JSONResponse:
        return problem_response(e.status, e.title, e.code, e.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException) -> JSONResponse:
        title = _TITLES.get(e.status_code, str(e.detail))
        return problem_response(e.status_code, title, "http_error", str(e.detail))

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(map(str, err['loc'][1:]))}: {err['msg']}" for err in e.errors())
        return problem_response(422, "Invalid request", "invalid_request", detail)
