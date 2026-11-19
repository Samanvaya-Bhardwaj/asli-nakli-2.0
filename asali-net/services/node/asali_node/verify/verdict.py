"""One verdict from the reasons (PLAN.md 12.3). No scores and no default: the strongest reason decides."""

from typing import Literal

from asali_node.verify.models import Reason

Verdict = Literal["genuine", "caution", "do_not_use", "cannot_check"]


def verdict_of(reasons: list[Reason]) -> Verdict:
    strengths = {r.strength for r in reasons}
    if "do_not_use" in strengths:  # missing sources are listed, but they do not block this
        return "do_not_use"
    if "cannot_check" in strengths:
        return "cannot_check"
    if "caution" in strengths:
        return "caution"
    return "genuine"
