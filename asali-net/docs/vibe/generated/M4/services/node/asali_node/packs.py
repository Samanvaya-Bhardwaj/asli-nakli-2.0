"""Making GTINs, lots and serials, and the label text for a pack (PLAN.md 9.1-9.2)."""

import secrets
from datetime import date
from urllib.parse import quote

from asali_codes.alphabet import ALPHABET
from asali_codes.checks import gs1_check_digit, luhn32_check_char
from asali_codes.read import format_serial

MONTH_LETTERS = "ABCDEFGHIJKL"
DIGITAL_LINK = "https://id.asali.example"


def make_gtin(gs1_prefix: str, item_number: int) -> str:
    """Indicator 0, the 7-digit company prefix, a 5-digit item reference and the GS1 check digit."""
    if len(gs1_prefix) != 7 or not gs1_prefix.isdigit():
        raise ValueError("the GS1 company prefix must be 7 digits")
    if not 0 <= item_number <= 99999:
        raise ValueError("the item reference must fit in 5 digits")
    body = f"0{gs1_prefix}{item_number:05d}"
    return body + gs1_check_digit(body)


def make_serial(issuer: str) -> str:
    payload = issuer + "".join(secrets.choice(ALPHABET) for _ in range(8))
    return payload + luhn32_check_char(payload)


def make_lot(issuer: str, mfg: date, number: int) -> str:
    """Each pharma has its own lot style: TP24A017, MV-2410-033, K/24/0091."""
    yy = f"{mfg.year % 100:02d}"
    if issuer == "TP":
        return f"TP{yy}{MONTH_LETTERS[mfg.month - 1]}{number:03d}"
    if issuer == "MV":
        return f"MV-{yy}{mfg.month:02d}-{number:03d}"
    if issuer == "KS":
        return f"K/{yy}/{number:04d}"
    raise ValueError(f"no lot style for issuer {issuer}")


def yymmdd(d: date) -> str:
    return f"{d.year % 100:02d}{d.month:02d}{d.day:02d}"


def digital_link(gtin: str, serial: str, lot: str, expiry: date) -> str:
    return f"{DIGITAL_LINK}/01/{gtin}/21/{serial}?10={quote(lot, safe='')}&17={yymmdd(expiry)}"


def label_line(gtin: str, serial: str, lot: str, expiry: date) -> str:
    return f"GTIN {gtin}   SN {format_serial(serial)}   LOT {lot}   EXP {expiry.month:02d}/{expiry.year}"
