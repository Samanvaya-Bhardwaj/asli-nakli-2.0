"""Phase 2 on recorded data: find codes that carry noise, propose the code that was meant, and apply it with a trail.

Noise is stopped at the door where it can be (scan sessions correct a reading before it is saved), but records
also arrive another way: a typed ledger, an import, an older system. This audits what an organisation has recorded
and cleans it with the same ingredients as a live scan: the weighted edit search, the check character, the set
of codes the makers actually issued, and the lot recorded beside the code.

Nothing is changed without a person: the audit only reports and proposes; applying a fix is a separate request that
is checked again and written to the organisation's own scan-correction table.
"""

import re
from typing import Any

from asali_codes.alphabet import ALPHABET, SERIAL_LENGTH
from asali_codes.candidates import Candidate
from asali_codes.checks import luhn32_is_valid

AUTO_MAX_COST, MAX_FIX_COST = 1.0, 2.0
LOT_COLUMN = re.compile(r"^(lot|lot_no|lot_number)$", re.I)


def syntax_problems(value: str, issuers: set[str]) -> list[str]:
    """Why a recorded code cannot be a code: its shape, its characters, its check character, its maker prefix."""
    out: list[str] = []
    if len(value) != SERIAL_LENGTH:
        out.append(f"has {len(value)} characters, a code has {SERIAL_LENGTH}")
    bad = sorted({c for c in value.upper() if c not in ALPHABET})
    if bad:
        out.append(f"contains {', '.join(bad)}, which a code never has")
    if len(value) == SERIAL_LENGTH and not bad and not luhn32_is_valid(value.upper()):
        out.append("the check character does not match the other characters")
    if issuers and value[:2].upper() not in issuers:
        out.append(f"no maker issues codes starting {value[:2].upper()}")
    return out


def choose(cands: list[Candidate]) -> Candidate | None:
    """One clear candidate: cheap enough, and well ahead of the next. Otherwise none: a person decides."""
    if not cands:
        return None
    best = cands[0]
    clear = len(cands) == 1 or cands[1].cost - best.cost >= 0.5
    return best if best.cost <= AUTO_MAX_COST and clear else None


def describe(c: Candidate, lot_fits: bool | None) -> dict[str, Any]:
    return {"serial": c.value, "cost": c.cost, "edits": list(c.edits), "lot_fits": lot_fits}
