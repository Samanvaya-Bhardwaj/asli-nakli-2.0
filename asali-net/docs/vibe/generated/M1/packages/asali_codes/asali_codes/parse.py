"""Turn cleaned input into GTIN, serial, lot and expiry fields (PLAN.md section 10.2 step 2-3)."""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from urllib.parse import parse_qs, unquote, urlsplit

from asali_codes.alphabet import SERIAL_LENGTH
from asali_codes.checks import gtin_is_valid, luhn32_is_valid
from asali_codes.dates import gs1_yymmdd, printed_expiry
from asali_codes.normalise import GS, normalise_raw, normalise_serial

FieldStatus = Literal["valid", "invalid_check", "invalid_char", "invalid_value", "wrong_length", "missing"]
Grammar = Literal["digital_link", "element_string", "label_line", "bare_serial", "bare_gtin", "unknown"]


@dataclass(frozen=True)
class Reading:
    raw: str
    grammar: Grammar
    gtin: str | None
    serial: str | None
    lot: str | None
    expiry: date | None
    status: dict[str, FieldStatus]
    notes: tuple[str, ...] = field(default=())


_FIXED_AI = {"01": 14, "11": 6, "17": 6}
_VARIABLE_AI = {"10": 20, "21": 20}
_LABEL = re.compile(
    r"(?i)(?<![A-Z0-9])(GTIN|S\s?/\s?N|S\.N\.?|SERIAL(?:\s*NO\.?)?|SN|LOT(?:\s*NO\.?)?|B\.?\s?NO\.?|"
    r"BATCH(?:\s*NO\.?)?|EXPIRY|EXP\.?|USE\s+BEFORE)(?![A-Z0-9])"
)


def parse(raw: str) -> Reading:
    text = normalise_raw(raw)
    if re.match(r"(?i)^https?://", text):
        fields = _digital_link(text)
        if fields:
            return _reading(raw, "digital_link", fields)
    if text.startswith("("):
        fields = _bracketed(text)
        if fields:
            return _reading(raw, "element_string", fields)
    compact = text.replace(" ", "")
    if re.fullmatch(r"01\d{14}[0-9A-Za-z\x1d/\-.]*", compact) and len(compact) > 16:
        fields = _best_ai_parse(compact)
        if fields:
            return _reading(raw, "element_string", fields)
    if _LABEL.search(text):
        fields = _label_line(text)
        if fields:
            return _reading(raw, "label_line", fields)
    return _bare(raw, text)


def _digital_link(text: str) -> dict[str, str]:
    parts = urlsplit(text)
    segs = [unquote(s) for s in parts.path.split("/") if s]
    fields: dict[str, str] = {}
    for i in range(len(segs) - 1):
        if segs[i] in ("01", "10", "21", "17") and segs[i] not in fields:
            fields[segs[i]] = segs[i + 1]
    for key, values in parse_qs(parts.query).items():
        if key in ("10", "17", "21") and key not in fields:
            fields[key] = values[0]
    return fields if "01" in fields else {}


def _bracketed(text: str) -> dict[str, str]:
    pieces = re.findall(r"\((\d{2})\)([^(]*)", text)
    return {ai: value.replace(GS, "").strip() for ai, value in pieces}


def _best_ai_parse(s: str) -> dict[str, str]:
    """Try every way the unterminated variable-length fields could end; prefer readings whose checks pass."""
    results: list[dict[str, str]] = []

    def is_ai_start(i: int) -> bool:
        return s[i : i + 2] in _FIXED_AI or s[i : i + 2] in _VARIABLE_AI

    def walk(i: int, acc: dict[str, str]) -> None:
        if len(results) > 64:
            return
        if i == len(s):
            results.append(acc)
            return
        ai = s[i : i + 2]
        if ai in acc:
            return
        if ai in _FIXED_AI:
            n = _FIXED_AI[ai]
            value = s[i + 2 : i + 2 + n]
            j = i + 2 + n
            if len(value) == n and value.isdigit():
                walk(j + 1 if s[j : j + 1] == GS else j, {**acc, ai: value})
        elif ai in _VARIABLE_AI:
            start = i + 2
            for end in range(start + 1, min(len(s), start + _VARIABLE_AI[ai]) + 1):
                if end == len(s) or s[end] == GS or is_ai_start(end):
                    walk(end + 1 if s[end : end + 1] == GS else end, {**acc, ai: s[start:end]})
                if end < len(s) and s[end] == GS:
                    break

    walk(0, {})
    if not results:
        return {}

    def score(f: dict[str, str]) -> tuple[bool, bool, int]:
        serial = normalise_serial(f.get("21", ""))[0]
        return (luhn32_is_valid(serial), gtin_is_valid(f.get("01", "")), len(f))

    return max(results, key=score)


def _label_line(text: str) -> dict[str, str]:
    matches = list(_LABEL.finditer(text))
    fields: dict[str, str] = {}
    for k, m in enumerate(matches):
        end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
        value = text[m.end() : end].strip(" :#-.\t")
        label = re.sub(r"[^A-Z]", "", m[1].upper())
        if label == "GTIN":
            fields.setdefault("01", re.sub(r"\s", "", value))
        elif label.startswith(("SN", "SERIAL")):
            fields.setdefault("21", value)
        elif label.startswith(("LOT", "BNO", "BATCH")):
            fields.setdefault("10", re.sub(r"\s", "", value))
        elif label.startswith(("EXP", "USEBEFORE")):
            fields.setdefault("exp_text", value)
    return fields


def _bare(raw: str, text: str) -> Reading:
    compact = re.sub(r"[\s\-–—]", "", text)
    if re.fullmatch(r"\d{14}", compact):
        return _reading(raw, "bare_gtin", {"01": compact})
    if re.fullmatch(r"\d{13}", compact):
        return _reading(raw, "bare_gtin", {"01": "0" + compact})
    if re.fullmatch(r"[0-9A-Za-z]{10,12}", compact) and not compact.isdigit():
        return _reading(raw, "bare_serial", {"21": text})
    return Reading(raw, "unknown", None, None, None, None, _missing_all())


def _missing_all() -> dict[str, FieldStatus]:
    return {"gtin": "missing", "serial": "missing", "lot": "missing", "expiry": "missing"}


def _reading(raw: str, grammar: Grammar, f: dict[str, str]) -> Reading:
    status = _missing_all()
    notes: list[str] = []
    gtin = f.get("01") or None
    if gtin is not None:
        if not gtin.isdigit():
            status["gtin"] = "invalid_char"
        elif len(gtin) != 14:
            status["gtin"] = "wrong_length"
        else:
            status["gtin"] = "valid" if gtin_is_valid(gtin) else "invalid_check"
    serial: str | None = None
    if f.get("21"):
        serial, serial_notes = normalise_serial(f["21"])
        notes += serial_notes
        if any("not in the code alphabet" in n for n in serial_notes):
            status["serial"] = "invalid_char"
        elif len(serial) != SERIAL_LENGTH:
            status["serial"] = "wrong_length"
        else:
            status["serial"] = "valid" if luhn32_is_valid(serial) else "invalid_check"
    lot = f.get("10") or None
    if lot is not None:
        status["lot"] = "valid" if 0 < len(lot) <= 20 else "wrong_length"
    expiry: date | None = None
    if "17" in f:
        expiry = gs1_yymmdd(f["17"])
        status["expiry"] = "valid" if expiry else "invalid_value"
    elif "exp_text" in f:
        expiry = printed_expiry(f["exp_text"])
        status["expiry"] = "valid" if expiry else "invalid_value"
    return Reading(raw, grammar, gtin, serial, lot, expiry, status, tuple(notes))
