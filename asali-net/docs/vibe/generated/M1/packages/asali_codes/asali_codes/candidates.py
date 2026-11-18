"""Codes the reader may have meant, cheapest first (PLAN.md section 10.2 step 4).

Serials: a best-first search over cheap edits (look-alike substitutions, swapped neighbours, doubled
keys), plus at most one full-cost edit, which the check character pins down: for any one position
there is exactly one character that makes the serial valid.
"""

import heapq
from collections.abc import Collection
from dataclasses import dataclass

from asali_codes.alphabet import ALPHABET, INDEX, SERIAL_LENGTH
from asali_codes.checks import gtin_is_valid, luhn32_is_valid
from asali_codes.confusion import (
    DOUBLED_KEY_COST,
    INDEL_COST,
    SERIAL_PARTNERS,
    TRANSPOSE_COST,
    substitution_cost,
    weighted_distance,
)

_N = len(ALPHABET)
_MAX_NODES = 4000


@dataclass(frozen=True)
class Candidate:
    value: str
    cost: float
    edits: tuple[str, ...] = ()


def _contribution(value: int, factor: int) -> int:
    product = factor * value
    return product // _N + product % _N


_SOLVE = {f: {_contribution(v, f) % _N: v for v in range(_N)} for f in (1, 2)}


def _solve_position(s: str, i: int) -> str | None:
    """The one character at position i that makes s pass the check, if the other characters allow it."""
    total = 0
    for k, ch in enumerate(reversed(s)):
        pos = len(s) - 1 - k
        if pos == i:
            continue
        if ch not in INDEX:
            return None
        total += _contribution(INDEX[ch], 1 if k % 2 == 0 else 2)
    factor = 1 if (len(s) - 1 - i) % 2 == 0 else 2
    return ALPHABET[_SOLVE[factor][(-total) % _N]]


def _cheap_edits(s: str) -> list[tuple[float, str, str]]:
    out: list[tuple[float, str, str]] = []
    for i, ch in enumerate(s):
        for partner, cost in SERIAL_PARTNERS.get(ch, []):
            out.append((cost, s[:i] + partner + s[i + 1 :], f"pos{i + 1} {ch}->{partner}"))
        if i + 1 < len(s) and s[i] != s[i + 1]:
            out.append((TRANSPOSE_COST, s[:i] + s[i + 1] + s[i] + s[i + 2 :], f"swap {i + 1}-{i + 2}"))
        if i > 0 and s[i] == s[i - 1]:
            out.append((DOUBLED_KEY_COST, s[:i] + s[i + 1 :], f"drop repeated {ch} at {i + 1}"))
    return out


def _one_full_edit(s: str) -> list[tuple[float, str, str]]:
    out: list[tuple[float, str, str]] = []
    if len(s) == SERIAL_LENGTH:
        for i, ch in enumerate(s):
            fix = _solve_position(s, i)
            if fix is not None and fix != ch:
                out.append((substitution_cost(fix, ch), s[:i] + fix + s[i + 1 :], f"pos{i + 1} {ch}->{fix}"))
    elif len(s) == SERIAL_LENGTH - 1:
        for i in range(len(s) + 1):
            padded = s[:i] + "0" + s[i:]
            fix = _solve_position(padded, i)
            if fix is not None:
                out.append((INDEL_COST, s[:i] + fix + s[i:], f"insert {fix} at {i + 1}"))
    elif len(s) == SERIAL_LENGTH + 1:
        for i, ch in enumerate(s):
            out.append((INDEL_COST, s[:i] + s[i + 1 :], f"drop {ch} at {i + 1}"))
    return out


def serial_candidates(
    seen: str, issuers: Collection[str], max_cost: float = 2.0, limit: int = 200
) -> list[Candidate]:
    seen = seen.upper()
    best: dict[str, float] = {seen: 0.0}
    heap: list[tuple[float, str, tuple[str, ...]]] = [(0.0, seen, ())]
    nodes: list[tuple[float, str, tuple[str, ...]]] = []
    while heap and len(nodes) < _MAX_NODES:
        cost, s, edits = heapq.heappop(heap)
        if cost > best.get(s, float("inf")):
            continue
        nodes.append((cost, s, edits))
        for step, s2, label in _cheap_edits(s):
            total = round(cost + step, 4)
            if total <= max_cost and total < best.get(s2, float("inf")):
                best[s2] = total
                heapq.heappush(heap, (total, s2, (*edits, label)))

    found: dict[str, Candidate] = {}

    def consider(value: str, cost: float, edits: tuple[str, ...]) -> None:
        if len(value) != SERIAL_LENGTH or not luhn32_is_valid(value):
            return
        if issuers and value[:2] not in issuers:
            return
        if value not in found or cost < found[value].cost:
            found[value] = Candidate(value, cost, edits)

    for cost, s, edits in nodes:
        consider(s, cost, edits)
        if cost + DOUBLED_KEY_COST <= max_cost:
            for step, s2, label in _one_full_edit(s):
                total = round(cost + step, 4)
                if total <= max_cost:
                    consider(s2, total, (*edits, label))
    return sorted(found.values(), key=lambda c: (c.cost, c.value))[:limit]


def gtin_candidates(seen: str, known_gtins: Collection[str], max_cost: float = 1.0) -> list[Candidate]:
    """GTINs are checked against the known product list; there are few enough to compare one by one."""
    out = []
    for g in known_gtins:
        if not gtin_is_valid(g):
            continue
        d = weighted_distance(g, seen)
        if d <= max_cost:
            out.append(Candidate(g, d))
    return sorted(out, key=lambda c: (c.cost, c.value))
