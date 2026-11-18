"""Check characters: GS1 mod-10 for GTINs, Luhn mod-32 for serials (PLAN.md section 9.3)."""

from asali_codes.alphabet import ALPHABET, INDEX

_N = len(ALPHABET)


def gs1_check_digit(body13: str) -> str:
    if len(body13) != 13 or not body13.isdigit():
        raise ValueError(f"GTIN body must be 13 digits, got {body13!r}")
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body13)))
    return str((10 - total % 10) % 10)


def gtin_is_valid(gtin14: str) -> bool:
    if len(gtin14) != 14 or not gtin14.isdigit():
        return False
    return gs1_check_digit(gtin14[:13]) == gtin14[13]


def luhn32_check_char(payload: str) -> str:
    factor, total = 2, 0
    for ch in reversed(payload):
        if ch not in INDEX:
            raise ValueError(f"{ch!r} is not in the serial alphabet")
        addend = factor * INDEX[ch]
        factor = 1 if factor == 2 else 2
        total += addend // _N + addend % _N
    return ALPHABET[(_N - total % _N) % _N]


def luhn32_is_valid(full: str) -> bool:
    if not full or any(ch not in INDEX for ch in full):
        return False
    factor, total = 1, 0
    for ch in reversed(full):
        addend = factor * INDEX[ch]
        factor = 2 if factor == 1 else 1
        total += addend // _N + addend % _N
    return total % _N == 0
