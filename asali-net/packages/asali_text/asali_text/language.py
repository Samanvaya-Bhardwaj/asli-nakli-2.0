"""Tag a text as English or Hinglish (Hindi in Latin letters) by the share of common Hinglish words (TEXT_ML.md 4.2)."""

import re

HINGLISH = frozenset(
    [
        "hai",
        "hain",
        "nahi",
        "nahin",
        "ka",
        "ki",
        "ke",
        "ko",
        "se",
        "mein",
        "liya",
        "liye",
        "kiya",
        "kiye",
        "tha",
        "thi",
        "aur",
        "par",
        "pe",
        "bhi",
        "abhi",
        "bahut",
        "dawai",
        "dawa",
        "goli",
        "alag",
        "koi",
        "fayda",
        "hua",
        "hui",
        "mera",
        "meri",
        "maine",
        "mujhe",
        "aap",
        "hum",
        "wahan",
        "yahan",
        "pichli",
        "pichle",
        "raha",
        "rahi",
        "sahi",
        "kharab",
        "jyada",
        "kam",
        "thoda",
        "lagta",
        "lag",
        "raha",
        "dukan",
        "wala",
        "wali",
        "ghante",
        "din",
        "raat",
        "subah",
        "shaam",
        "kal",
        "aaj",
        "paise",
        "rupaye",
        "wapas",
        "dena",
        "diya",
        "dikh",
        "dikha",
        "asli",
        "nakli",
    ]
)
THRESHOLD = 0.15
_WORD = re.compile(r"[a-z]+")


def language_of(text: str) -> str:
    words = _WORD.findall(text.lower())
    if not words:
        return "en"
    return "hi-Latn" if sum(w in HINGLISH for w in words) / len(words) >= THRESHOLD else "en"
