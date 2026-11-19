"""Words and marks the interface and its generated sentences must not use (DESIGN.md 10.2 rules 4 and 5)."""

import re

BANNED_WORDS = (
    "seamless", "robust", "powerful", "cutting-edge", "leverage", "empower", "unlock", "effortless",
    "streamline", "delve", "journey", "ecosystem", "solution", "revolutionary",
)  # fmt: skip
_WORD = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")\w*", re.IGNORECASE)
EM_DASH = "—"


def problems_in(text: str) -> list[str]:
    """What is wrong with a sentence meant for people: banned words, exclamation marks, em dashes."""
    found = [m.group(0).lower() for m in _WORD.finditer(text)]
    if "!" in text:
        found.append("exclamation mark")
    if EM_DASH in text:
        found.append("em dash")
    return found
