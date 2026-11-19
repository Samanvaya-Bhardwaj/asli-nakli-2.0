"""Small accessors for what create_app puts on app.state, so routes stay short."""

from datetime import datetime
from typing import Any

from fastapi import Request

from asali_node.canonical import IST
from asali_node.problems import Problem
from asali_node.settings import Settings


def settings_of(request: Request) -> Settings:
    s: Settings = request.app.state.settings
    return s


def rw(request: Request) -> Any:
    """The read-write store: only portal routes use it."""
    return request.app.state.rw


def ro(request: Request) -> Any:
    """The read-only store: the share API only ever uses this one."""
    return request.app.state.ro


def need_type(request: Request, *types: str) -> None:
    s = settings_of(request)
    if s.org_type not in types:
        raise Problem(404, "Not found", "not_served", f"{s.org_name} does not hold this kind of information.")


def effective_at(request: Request, at: datetime | None) -> datetime:
    """Portal writes are stamped now. Only simulation mode accepts an explicit time, for seeding."""
    if at is None:
        return datetime.now(IST)
    if settings_of(request).asali_mode != "simulation":
        raise Problem(
            400, "Time cannot be set", "at_not_allowed", "Records are stamped with the current time."
        )
    return at if at.tzinfo else at.replace(tzinfo=IST)
