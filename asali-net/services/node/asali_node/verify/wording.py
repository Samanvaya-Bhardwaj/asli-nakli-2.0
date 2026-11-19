"""The sentences a person reads (DESIGN.md 6.2 and 10): conclusion first, reason next, what to do last."""

from datetime import date

from asali_node.canonical import Event
from asali_node.verify.models import Facts, Reason
from asali_node.verify.verdict import Verdict

WORD: dict[Verdict, str] = {
    "genuine": "Genuine",
    "caution": "Caution",
    "do_not_use": "Do not use",
    "cannot_check": "Cannot check",
}
DO_NOT_TAKE = (
    "Do not take this medicine. Show this result to the pharmacist or call the drug control helpline."
)
RETRY = "Try again in a few minutes."


def long_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _where(f: Facts, e: Event) -> str:
    return f"{f.names.get(e.org_id, e.org_id)}, {e.city}"


def _genuine(f: Facts) -> str:
    maker = f.names.get(f.chain[0].org_id, "the maker") if f.chain else "the maker"
    events = sorted((e for h in f.chain if h.view for e in h.view.events), key=lambda e: e.at)
    sold = [e for e in events if e.event_type == "sell"]
    if sold:
        return f"Made by {maker}, sold by {_where(f, sold[-1])} on {long_date(sold[-1].at.date())}."
    received = [e for e in events if e.event_type == "receive"]
    if received:
        last = received[-1]
        who = f.names.get(last.org_id, last.org_id)
        return f"Made by {maker}. {who} received it on {long_date(last.at.date())} and has not recorded a sale yet."
    return f"Made by {maker}. It has not left the maker yet."


def describe(verdict: Verdict, reasons: list[Reason], f: Facts) -> dict[str, str]:
    """The verdict word, one headline sentence, and what to do. Wording follows the strongest reason."""
    strongest = next((r for r in reasons if r.strength == verdict), None)
    if verdict == "genuine":
        return {"word": WORD[verdict], "headline": f"Genuine. {_genuine(f)}", "action": ""}
    if verdict == "do_not_use" and strongest:
        return {
            "word": WORD[verdict],
            "headline": f"Do not use this pack. {strongest.text}",
            "action": DO_NOT_TAKE,
        }
    if verdict == "cannot_check" and strongest:
        who = strongest.text.removesuffix(" did not answer.")
        return {"word": WORD[verdict], "action": RETRY,
                "headline": f"We could not check this pack. {who} did not answer, so we cannot see the whole route."}  # fmt: skip
    if verdict == "caution" and strongest:
        return {"word": WORD[verdict], "headline": f"Be careful with this pack. {strongest.text}",
                "action": "Ask the pharmacist to look at it before you take it."}  # fmt: skip
    return {"word": WORD[verdict], "headline": "", "action": ""}
