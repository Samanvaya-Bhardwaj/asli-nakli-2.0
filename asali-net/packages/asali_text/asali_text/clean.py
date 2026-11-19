"""Clean and redact text before it is stored (TEXT_ML.md 4.1): phone numbers, e-mails, long ids."""

import re
import unicodedata

PHONE = re.compile(r"(?<![\d.])(?:\+?91[\s-]?)?(?:0[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LONG_ID = re.compile(r"(?<![\d.])\d{12}(?!\d)")  # an Aadhaar-length number
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalise(text: str) -> str:
    """NFKC, no control characters, single spaces within a line, at most one blank line in a row."""
    text = CONTROL.sub("", unicodedata.normalize("NFKC", text))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def redact(text: str) -> tuple[str, list[str]]:
    """Return the text with personal details replaced, and the kinds that were found."""
    found: list[str] = []
    for kind, pattern, token in (
        ("email", EMAIL, "[email]"),
        ("id", LONG_ID, "[id]"),
        ("phone", PHONE, "[phone]"),
    ):
        text, n = pattern.subn(token, text)
        if n:
            found.append(kind)
    return text, found
