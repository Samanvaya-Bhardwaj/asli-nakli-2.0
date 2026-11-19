"""Staff sign-in: bcrypt passwords, an in-memory session table, an HttpOnly cookie (PLAN.md 11.6)."""

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

import bcrypt
from fastapi import Request

from asali_node.canonical import StaffRecord
from asali_node.problems import Problem

COOKIE = "asali_session"
TTL_S = 8 * 3600


@dataclass(frozen=True)
class Session:
    username: str
    role: str
    display_name: str
    expires: float


class SessionTable:
    def __init__(self, clock: Any = time.time) -> None:
        self._rows: dict[str, Session] = {}
        self._clock = clock

    def create(self, rec: StaffRecord) -> str:
        token = secrets.token_urlsafe(32)
        self._rows[token] = Session(rec.username, rec.role, rec.display_name, self._clock() + TTL_S)
        return token

    def get(self, token: str | None) -> Session | None:
        row = self._rows.get(token or "")
        if row is None or row.expires < self._clock():
            self._rows.pop(token or "", None)
            return None
        return row

    def drop(self, token: str | None) -> None:
        self._rows.pop(token or "", None)


def hash_password(password: str) -> str:
    rounds = int(os.environ.get("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds)).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def seed_staff(store: Any, seed_json: str | None) -> int:
    """Create the staff listed in STAFF_SEED_JSON that do not exist yet. Returns how many were created."""
    created = 0
    for item in json.loads(seed_json) if seed_json else []:
        if store.get_staff(item["username"]) is None:
            store.add_staff(
                StaffRecord(
                    username=item["username"],
                    password_hash=hash_password(item["password"]),
                    role=item.get("role", "operator"),
                    display_name=item.get("display_name", item["username"]),
                )
            )
            created += 1
    return created


def current_staff(request: Request) -> Session:
    table: SessionTable = request.app.state.sessions
    session = table.get(request.cookies.get(COOKIE))
    if session is None:
        raise Problem(401, "Not signed in", "not_signed_in", "Sign in to continue.")
    return session
