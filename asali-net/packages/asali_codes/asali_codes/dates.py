"""Expiry dates as printed on packs. A month without a day means the last day of that month."""

import calendar
import re
from datetime import date

_MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
_MONTH_NAMES = {m.upper(): i for i, m in enumerate(calendar.month_name) if m}


def _year(text: str) -> int:
    y = int(text)
    return 2000 + y if y < 100 else y


def _last_day(year: int, month: int) -> date | None:
    if not 1 <= month <= 12 or not 2000 <= year <= 2099:
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def gs1_yymmdd(text: str) -> date | None:
    """GS1 AI 17: YYMMDD, where DD=00 means the last day of the month."""
    if len(text) != 6 or not text.isdigit():
        return None
    year, month, day = 2000 + int(text[:2]), int(text[2:4]), int(text[4:])
    return _last_day(year, month) if day == 0 else _safe(year, month, day)


def printed_expiry(text: str) -> date | None:
    """Parse forms like 03/2027, 03/27, MAR 2027, MAR.27, March 2027, 2027-03, 31/03/2027, 2027-03-31."""
    t = text.strip().upper().rstrip(".")
    if m := re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})", t):
        return _safe(_year(m[3]), int(m[2]), int(m[1]))
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t):
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    if m := re.fullmatch(r"(\d{1,2})\s*[/.\-]\s*(\d{2}|\d{4})", t):
        return _last_day(_year(m[2]), int(m[1]))
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})", t):
        return _last_day(int(m[1]), int(m[2]))
    if m := re.fullmatch(r"([A-Z]{3,9})[\s.\-/']*(\d{2}|\d{4})", t):
        month = _MONTHS.get(m[1][:3]) if m[1] not in _MONTH_NAMES else _MONTH_NAMES[m[1]]
        return _last_day(_year(m[2]), month) if month else None
    return None
