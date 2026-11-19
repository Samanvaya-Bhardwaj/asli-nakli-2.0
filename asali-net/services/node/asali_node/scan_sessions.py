"""A staff scan session: rows read against an expected set, with correction, duplicates and undo.

Sessions live in memory with a 2 hour time-to-live (TASKS.md 4.4). Nothing here touches a database;
finishing a session hands the accepted units to the portal route, which writes them.
"""

import secrets
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from typing import Any, Literal

from asali_codes.read import format_serial, read

from asali_node.canonical import UnitRef
from asali_node.problems import Problem

TTL_S = 2 * 3600
Kind = Literal["dispatch", "receive", "sell", "return"]
Source = Literal["wedge", "camera", "typed"]
BLOCKING = {"needs_choice", "unreadable", "not_expected"}
COUNTED = {"ok", "corrected"}
NOT_IN = {
    "dispatch": "Not in your stock.",
    "sell": "Not in your stock.",
    "receive": "Not in this shipment.",
    "return": "This pack was not sold here, or it was already returned.",
}


@dataclass
class Row:
    row_id: int
    raw: str
    status: str
    message: str = ""
    gtin: str | None = None
    serial: str | None = None
    lot: str | None = None
    expiry: str | None = None
    corrected_from: str | None = None
    cost: float | None = None
    choices: list[str] = field(default_factory=list)

    def view(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id, "raw": self.raw, "status": self.status, "message": self.message,
            "gtin": self.gtin, "serial": self.serial, "lot": self.lot, "expiry": self.expiry,
            "corrected_from": self.corrected_from, "choices": self.choices,
        }  # fmt: skip


class ScanSession:
    def __init__(
        self,
        kind: Kind,
        expected: dict[tuple[str, str], UnitRef],
        issuers: Collection[str],
        *,
        to_org: str | None = None,
        from_org: str | None = None,
        source_ref: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.session_id = secrets.token_urlsafe(9)
        self.kind, self.expected, self.issuers = kind, expected, issuers
        self.to_org, self.from_org, self.source_ref = to_org, from_org, source_ref
        self._clock = clock
        self.expires = clock() + TTL_S
        self.rows: list[Row] = []
        self._next = 1

    # ---- reading ----
    def _active(self) -> list[Row]:
        return [r for r in self.rows if r.status != "removed"]

    def _row(self, raw: str, status: str, message: str = "", **kw: Any) -> Row:
        row = Row(self._next, raw, status, message, **kw)
        self._next += 1
        return row

    def read(self, raw: str) -> Row:
        res = read(raw, context="staff", issuers=self.issuers, expected=set(self.expected))
        if res.decision == "unreadable":
            return self._add(self._row(raw, "unreadable", res.message))
        if res.decision == "needs_choice":
            choices = [c.value for c in res.choices]
            return self._add(self._row(raw, "needs_choice", res.message, choices=choices))
        serial = res.serial or ""
        gtin = res.gtin or self._gtin_for(serial)
        if gtin is None:
            return self._add(
                self._row(raw, "unreadable", "This code does not name a product. Scan the QR code.")
            )
        key = (gtin, serial)
        if any(r.status in COUNTED and (r.gtin, r.serial) == key for r in self.rows):
            return self._row(raw, "duplicate", "Already scanned in this session.", gtin=gtin, serial=serial)
        unit = self.expected.get(key)
        if unit is None:
            return self._add(self._row(raw, "not_expected", NOT_IN[self.kind], gtin=gtin, serial=serial))
        corrected = res.decision == "corrected"
        return self._add(
            self._row(
                raw, "corrected" if corrected else "ok", res.message, gtin=gtin, serial=serial,
                lot=unit.lot, expiry=unit.expiry.isoformat() if unit.expiry else None,
                corrected_from=raw if corrected else None,
                cost=res.chosen.cost if corrected and res.chosen else None,
            )
        )  # fmt: skip

    def _gtin_for(self, serial: str) -> str | None:
        gtins = {g for g, s in self.expected if s == serial}
        return gtins.pop() if len(gtins) == 1 else None

    def _add(self, row: Row) -> Row:
        self.rows.insert(0, row)
        return row

    # ---- editing ----
    def _find(self, row_id: int) -> Row:
        for r in self.rows:
            if r.row_id == row_id and r.status != "removed":
                return r
        raise Problem(404, "Not found", "unknown_row", "That row is not in this session.")

    def undo(self, row_id: int) -> None:
        self._find(row_id).status = "removed"

    def choose(self, row_id: int, serial: str) -> Row:
        row = self._find(row_id)
        if row.status != "needs_choice" or serial not in row.choices:
            raise Problem(409, "Not a choice", "bad_choice", "Pick one of the codes offered for this row.")
        gtin = self._gtin_for(serial)
        unit = self.expected.get((gtin, serial)) if gtin else None
        if unit is None:
            raise Problem(409, "Not a choice", "bad_choice", "That code is not expected in this session.")
        if any(r.status in COUNTED and r.serial == serial for r in self.rows):
            row.status, row.message = "removed", ""
            raise Problem(409, "Already scanned", "duplicate", "Already scanned in this session.")
        row.status, row.gtin, row.serial, row.corrected_from = "corrected", gtin, serial, row.raw
        row.lot, row.expiry = unit.lot, unit.expiry.isoformat() if unit.expiry else None
        row.message = f"Read as {row.raw}, corrected to {format_serial(serial)}."
        row.choices = []
        return row

    # ---- results ----
    def counts(self) -> dict[str, int]:
        active = self._active()
        return {
            "scanned": sum(r.status in COUNTED for r in active),
            "needs_attention": sum(r.status in BLOCKING for r in active),
            "expected": len(self.expected) if self.kind == "receive" else 0,
        }

    def units(self) -> list[UnitRef]:
        """The accepted units, oldest scan first. Refuses while any row still needs a decision."""
        if any(r.status in BLOCKING for r in self._active()):
            raise Problem(
                409,
                "Rows need a decision",
                "unresolved_rows",
                "Remove or fix the rows marked with a cross first.",
            )
        out = []
        for r in reversed(self._active()):
            if r.status in COUNTED and r.gtin and r.serial:
                base = self.expected[(r.gtin, r.serial)]
                out.append(base.model_copy(update={"raw": r.raw, "corrected": r.status == "corrected"}))
        if not out:
            raise Problem(409, "Nothing scanned", "empty_session", "Scan at least one pack first.")
        return out

    def missing(self) -> list[UnitRef]:
        done = {(r.gtin, r.serial) for r in self._active() if r.status in COUNTED}
        return [u for k, u in sorted(self.expected.items()) if k not in done]

    def corrections(self) -> list[Row]:
        return [r for r in self._active() if r.status == "corrected"]


class SessionTable:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._rows: dict[str, ScanSession] = {}
        self._clock = clock

    def add(self, session: ScanSession) -> ScanSession:
        self._rows = {k: v for k, v in self._rows.items() if v.expires > self._clock()}
        self._rows[session.session_id] = session
        return session

    def get(self, session_id: str) -> ScanSession:
        s = self._rows.get(session_id)
        if s is None or s.expires < self._clock():
            self._rows.pop(session_id, None)
            raise Problem(
                410, "Session ended", "session_expired", "This scan session expired. Start a new one."
            )
        return s

    def drop(self, session_id: str) -> None:
        self._rows.pop(session_id, None)
