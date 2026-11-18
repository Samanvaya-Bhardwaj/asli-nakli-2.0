"""Clean raw scanner or typed input before parsing (PLAN.md section 10.2 step 1)."""

import re
import unicodedata

from asali_codes.alphabet import DECODE_ALIASES, INDEX

GS = "\x1d"
_SYMBOLOGY_PREFIX = re.compile(r"^\](?:Q1|Q3|d2|C1)")
_SERIAL_SEPARATORS = frozenset(" -\u2010\u2011\u2012\u2013\u2014\u2015\u2212_.\t")


def normalise_raw(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw).strip()
    text = "".join(ch for ch in text if ch == GS or unicodedata.category(ch)[0] != "C")
    return _SYMBOLOGY_PREFIX.sub("", text).strip()


def normalise_serial(text: str) -> tuple[str, list[str]]:
    """Uppercase, drop separators, map O/I/L to digits. Report anything else that is not in the alphabet."""
    out: list[str] = []
    notes: list[str] = []
    for ch in text.upper():
        if ch in _SERIAL_SEPARATORS:
            continue
        if ch in DECODE_ALIASES:
            notes.append(f"read {ch} as {DECODE_ALIASES[ch]} at position {len(out) + 1}")
            out.append(DECODE_ALIASES[ch])
        elif ch in INDEX:
            out.append(ch)
        else:
            notes.append(f"{ch!r} at position {len(out) + 1} is not in the code alphabet")
            out.append(ch)
    return "".join(out), notes
