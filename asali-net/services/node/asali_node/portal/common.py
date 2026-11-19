"""Sign in, sign out, who am I. Consumer routes (/api/check, /api/report) need no session."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from asali_node import deps
from asali_node.auth.staff import COOKIE, TTL_S, Session, SessionTable, check_password, current_staff
from asali_node.problems import Problem

router = APIRouter(prefix="/api")


class Login(BaseModel):
    username: str
    password: str


def _who(request: Request, s: Session) -> dict[str, Any]:
    cfg = deps.settings_of(request)
    return {"username": s.username, "role": s.role, "display_name": s.display_name,
            "org_id": cfg.org_id, "org_type": cfg.org_type}  # fmt: skip


@router.post("/login")
def login(body: Login, request: Request, response: Response) -> dict[str, Any]:
    rec = deps.rw(request).get_staff(body.username)
    if rec is None or not check_password(body.password, rec.password_hash):
        raise Problem(401, "Not signed in", "bad_credentials", "Wrong username or password.")
    table: SessionTable = request.app.state.sessions
    token = table.create(rec)
    response.set_cookie(COOKIE, token, max_age=TTL_S, httponly=True, samesite="lax", path="/")
    return _who(request, table.get(token))  # type: ignore[arg-type]


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    request.app.state.sessions.drop(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/me")
def me(request: Request, session: Session = Depends(current_staff)) -> dict[str, Any]:
    return _who(request, session)
