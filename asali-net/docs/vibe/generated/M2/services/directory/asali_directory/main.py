"""Network directory (PLAN.md section 8.1): addresses and public keys of every organisation."""

import base64
import binascii
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from asali_directory.settings import Settings
from asali_directory.store import Store

OrgType = Literal["pharma", "distributor", "shop", "consumer", "regulator"]


class Problem(Exception):
    def __init__(self, status: int, title: str, code: str, detail: str = "") -> None:
        self.status, self.title, self.code, self.detail = status, title, code, detail


def _problem(status: int, title: str, code: str, detail: str = "") -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, "code": code}
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


class OrgIn(BaseModel):
    org_id: str
    org_type: OrgType
    name: str
    city: str
    state: str
    issuer_code: str | None = None
    gs1_prefix: str | None = None
    base_url: str
    public_key: str
    host_name: str

    @field_validator("org_id")
    @classmethod
    def _org_id(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,31}", v):
            raise ValueError("org_id is 2-32 lowercase letters, digits or hyphens")
        return v

    @field_validator("issuer_code")
    @classmethod
    def _issuer(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{2}", v):
            raise ValueError("issuer_code is 2 characters of the code alphabet (no I, L, O, U)")
        return v

    @field_validator("gs1_prefix")
    @classmethod
    def _prefix(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{6,10}", v):
            raise ValueError("gs1_prefix is 6-10 digits")
        return v

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not re.fullmatch(r"https?://[^\s/]+(:\d+)?/?", v):
            raise ValueError("base_url is http(s)://host:port")
        return v.rstrip("/")

    @field_validator("public_key")
    @classmethod
    def _key(cls, v: str) -> str:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(v, validate=True))
        except (ValueError, binascii.Error):
            raise ValueError("public_key is a base64 Ed25519 public key") from None
        return v


def create_app(settings: Settings, clock: Callable[[], float] = time.time) -> FastAPI:
    store = Store(settings.data_dir)
    app = FastAPI(title="Asali directory", version="1")

    @app.exception_handler(Problem)
    async def _on_problem(_: Request, e: Problem) -> JSONResponse:
        return _problem(e.status, e.title, e.code, e.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _on_http(_: Request, e: StarletteHTTPException) -> JSONResponse:
        return _problem(e.status_code, str(e.detail), "http_error")

    @app.exception_handler(RequestValidationError)
    async def _on_invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(map(str, err['loc'][1:]))}: {err['msg']}" for err in e.errors())
        return _problem(422, "Invalid request", "invalid_request", detail)

    def out(org: dict[str, Any]) -> dict[str, Any]:
        o = {k: v for k, v in org.items() if k not in ("registered_at", "last_seen")}
        o["online"] = clock() - org["last_seen"] < settings.online_window_s
        o["last_seen"] = datetime.fromtimestamp(org["last_seen"], UTC).isoformat()
        return o

    def found(org: dict[str, Any] | None, what: str) -> dict[str, Any]:
        if org is None:
            raise Problem(404, f"No organisation for {what}", "not_found")
        return out(org)

    @app.get("/directory/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/directory/v1/register", status_code=201)
    def register(
        body: OrgIn,
        x_join_token: str = Header(default=""),
        x_admin_token: str = Header(default=""),
    ) -> JSONResponse:
        if x_join_token != settings.join_token:
            raise Problem(401, "Wrong network join token", "bad_join_token")
        existing = store.get(body.org_id)
        if existing and existing["public_key"] != body.public_key and x_admin_token != settings.admin_token:
            raise Problem(
                409, "This organisation is registered with a different key", "key_conflict",
                "Re-registering with a new key needs the admin token.",
            )  # fmt: skip
        created = store.upsert(body.model_dump(), clock())
        return JSONResponse(out(store.get(body.org_id) or {}), status_code=201 if created else 200)

    @app.post("/directory/v1/heartbeat")
    def heartbeat(request: Request) -> dict[str, str]:
        org_id = _verify(request, store, clock(), settings.max_clock_skew_s)
        store.touch(org_id, clock())
        return {"status": "ok"}

    @app.get("/directory/v1/orgs")
    def orgs(type: OrgType | None = None, state: str | None = None) -> list[dict[str, Any]]:
        return [out(o) for o in store.list(type, state)]

    @app.get("/directory/v1/orgs/{org_id}")
    def org(org_id: str) -> dict[str, Any]:
        return found(store.get(org_id), org_id)

    @app.get("/directory/v1/issuers/{code}")
    def issuer(code: str) -> dict[str, Any]:
        return found(store.by_issuer(code.upper()), f"issuer code {code}")

    @app.get("/directory/v1/prefixes/{gtin}")
    def prefix(gtin: str) -> dict[str, Any]:
        return found(store.by_gtin(gtin) if gtin.isdigit() and len(gtin) == 14 else None, f"GTIN {gtin}")

    return app


def _verify(request: Request, store: Store, now: float, max_skew: int) -> str:
    """Check the same Ed25519 request signature the nodes use (PLAN.md section 8.2)."""
    org_id = request.headers.get("x-asali-org", "")
    stamp = request.headers.get("x-asali-time", "")
    sig = request.headers.get("x-asali-signature", "")
    org = store.get(org_id)
    if org is None:
        raise Problem(401, "Unknown organisation", "unknown_org")
    if not stamp.isdigit() or abs(now - int(stamp)) > max_skew:
        raise Problem(401, "Request time is too far from the directory's clock", "clock_skew")
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    message = f"{request.method}\n{path}\n{stamp}\n{org_id}".encode()
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(org["public_key"]))
        key.verify(base64.b64decode(sig), message)
    except (InvalidSignature, ValueError, binascii.Error):
        raise Problem(401, "Signature does not match", "bad_signature") from None
    return org_id


def app_from_env() -> FastAPI:
    return create_app(Settings())  # type: ignore[call-arg]
