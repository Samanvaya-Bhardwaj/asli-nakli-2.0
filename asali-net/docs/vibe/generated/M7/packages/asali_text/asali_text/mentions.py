"""Find codes, names, dates and temperatures in text with rules and a gazetteer (TEXT_ML.md 4.4).

Codes have a grammar, so rules find them more reliably than a classifier. Every mention keeps its span.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from asali_codes.checks import luhn32_is_valid
from asali_codes.normalise import normalise_serial
from rapidfuzz import fuzz

from asali_text.gazetteer import CITY_VARIANTS, Gazetteer

MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
DIGITS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "i": "1"})


@dataclass(frozen=True)
class Mention:
    kind: str
    text: str
    start: int
    end: int
    value: Any = None
    valid: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "text": self.text, "span": [self.start, self.end], "value": self.value, "valid": self.valid}


def _add(out: list[Mention], kind: str, m: re.Match[str], value: Any = None, valid: bool | None = None, group: int = 0) -> None:
    out.append(Mention(kind, m.group(group), m.start(group), m.end(group), value, valid))


def _serials(text: str, issuers: tuple[str, ...], out: list[Mention]) -> None:
    pat = re.compile(rf"(?<![A-Za-z0-9])((?:{'|'.join(issuers)})[0-9A-Za-z]{{2}}[ -]?[0-9A-Za-z]{{4}}[ -]?[0-9A-Za-z]{{3}})(?![A-Za-z0-9])", re.I)
    for m in pat.finditer(text):
        serial, problems = normalise_serial(m.group(1))
        _add(out, "serial", m, serial, valid=not problems and len(serial) == 11 and luhn32_is_valid(serial), group=1)


def _canon_lot(parts: list[str], style: str) -> str:
    if style == "TP":
        return f"TP{parts[0].translate(DIGITS)}{parts[1].upper()}{parts[2].translate(DIGITS)}"
    if style == "MV":
        return f"MV-{parts[0].translate(DIGITS)}-{parts[1].translate(DIGITS)}"
    return f"K/{parts[0].translate(DIGITS)}/{parts[1].translate(DIGITS)}"


LOT_PATTERNS = [
    ("TP", re.compile(r"(?<![A-Za-z0-9])TP ?([0-9OIl]{2}) ?([A-La-l]) ?([0-9OIl]{3})(?![A-Za-z0-9])", re.I)),
    ("MV", re.compile(r"(?<![A-Za-z0-9])MV[- ]?([0-9OIl]{4})[- ]?([0-9OIl]{3})(?![A-Za-z0-9])", re.I)),
    ("K", re.compile(r"(?<![A-Za-z0-9])K ?[/-] ?([0-9OIl]{2}) ?[/-] ?([0-9OIl]{4})(?![0-9A-Za-z])", re.I)),
]


def _lots(text: str, out: list[Mention]) -> None:
    for style, pat in LOT_PATTERNS:
        for m in pat.finditer(text):
            _add(out, "lot", m, _canon_lot(list(m.groups()), style))


def _refs_and_gtins(text: str, out: list[Mention]) -> None:
    for m in re.finditer(r"(?<![A-Za-z0-9])(?:DSP|SHP|CN)-[A-Za-z0-9-]{4,}", text, re.I):
        _add(out, "shipment_ref", m, m.group(0).rstrip("-.,").upper().replace("SHP-", "SHP-"))
    for m in re.finditer(r"(?<![0-9A-Za-z])0?[0-9]{13}(?![0-9A-Za-z])", text):
        _add(out, "gtin", m, m.group(0).zfill(14))


def _words(text: str) -> list[tuple[str, int, int]]:
    return [(w.group(0), w.start(), w.end()) for w in re.finditer(r"[A-Za-z][A-Za-z0-9.-]*", text)]


def _phrase_match(text: str, words: list[tuple[str, int, int]], form: str, minimum: int) -> tuple[int, int, float] | None:
    """The best window of as many words as the form has, compared one phrase against the other."""
    n = len(form.split())
    best: tuple[int, int, float] | None = None
    for i in range(len(words) - n + 1):
        s, e = words[i][1], words[i + n - 1][2]
        score = fuzz.ratio(form, text[s:e].lower())
        if score >= minimum and (best is None or score > best[2]):
            best = (s, e, score)
    return best


def _names(text: str, gaz: Gazetteer, out: list[Mention]) -> None:
    words = _words(text)
    for p in gaz.products:
        for label, form in (("brand", p.brand), ("generic", p.generic)):
            hit = _phrase_match(text, words, form.lower(), 85) if len(form) >= 5 else None
            if hit:
                out.append(Mention("product", text[hit[0] : hit[1]], hit[0], hit[1], {"gtin": p.gtin, "by": label}))
    best: dict[str, Mention] = {}
    for form, org_id in gaz.org_forms():
        hit = _phrase_match(text, words, form, 85)
        if hit and (org_id not in best or hit[2] > best[org_id].value["score"]):
            best[org_id] = Mention("org", text[hit[0] : hit[1]], hit[0], hit[1], {"org_id": org_id, "score": hit[2]})
    out.extend(best.values())
    for name, canon in CITY_VARIANTS.items():
        for m in re.finditer(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", text, re.I):
            _add(out, "city", m, canon)


def _dates_and_numbers(text: str, year: int, out: list[Mention]) -> None:
    for m in re.finditer(r"(?<![\d/.-])(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?![\d/-])", text):
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if y < 100 else 0
        if 1 <= d <= 31 and 1 <= mo <= 12:
            _add(out, "date", m, date(y, mo, d).isoformat() if _ok(y, mo, d) else None)
    for m in re.finditer(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?=\s+\d{1,2}:\d{2})", text):
        d, mo = int(m[1]), int(m[2])
        if 1 <= d <= 31 and 1 <= mo <= 12 and _ok(year, mo, d):
            _add(out, "date", m, date(year, mo, d).isoformat())
    for m in re.finditer(r"\b(\d{1,2})\s?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b(?:,?\s?(\d{4}))?", text, re.I):
        d, mo, y = int(m[1]), MONTHS[m[2].lower()], int(m[3] or year)
        if 1 <= d <= 31 and _ok(y, mo, d):
            _add(out, "date", m, date(y, mo, d).isoformat())
    for m in re.finditer(r"\b(?:exp(?:iry|ires)?\.?|use before|best before)\s*[:.]?\s*(\d{1,2}/\d{4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? ?\d{4})", text, re.I):
        raw = m.group(1)
        if "/" in raw:
            mo, y = (int(x) for x in raw.split("/"))
        else:
            mo, y = MONTHS[raw[:3].lower()], int(raw[-4:])
        _add(out, "expiry", m, f"{y:04d}-{mo:02d}" if 1 <= mo <= 12 else None, group=1)
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s?(?:°|º|deg(?:rees)?)?\s?C(?![A-Za-z])", text):
        _add(out, "temperature", m, float(m[1]))
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s?(?:h|hr|hrs|hours?|ghante)\b(?:\s*(\d{1,2})\s?(?:min|minutes)\b)?", text, re.I):
        _add(out, "duration", m, int(m[1]) * 60 + int(m[2] or 0))
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s?(mg|mcg|ml|iu)\b", text, re.I):
        _add(out, "strength", m, f"{m[1]} {m[2].lower() if m[2].lower() != 'iu' else 'IU'}")


def _ok(y: int, mo: int, d: int) -> bool:
    try:
        date(y, mo, d)
    except ValueError:
        return False
    return True


def extract(text: str, gaz: Gazetteer, year: int = 2026) -> list[Mention]:
    out: list[Mention] = []
    _serials(text, gaz.issuers, out)
    _lots(text, out)
    _refs_and_gtins(text, out)
    _names(text, gaz, out)
    _dates_and_numbers(text, year, out)
    return sorted(out, key=lambda m: (m.start, m.kind))


def by_kind(mentions: list[Mention], kind: str) -> list[Mention]:
    return [m for m in mentions if m.kind == kind]
