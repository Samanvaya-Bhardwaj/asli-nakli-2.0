import pytest
from asali_codes.alphabet import ALPHABET
from asali_codes.checks import gs1_check_digit, gtin_is_valid, luhn32_check_char, luhn32_is_valid
from vectors import V


def test_alphabet_matches_vectors() -> None:
    assert V["crockford_alphabet"] == ALPHABET
    assert len(ALPHABET) == 32
    assert not set("ILOU") & set(ALPHABET)


@pytest.mark.parametrize("gtin", V["gtin_valid"])
def test_valid_gtins(gtin: str) -> None:
    assert gtin_is_valid(gtin)
    assert gs1_check_digit(gtin[:13]) == gtin[13]


@pytest.mark.parametrize("gtin", V["gtin_invalid"])
def test_invalid_gtins(gtin: str) -> None:
    assert not gtin_is_valid(gtin)


@pytest.mark.parametrize("bad", ["", "123", "0890100100012X", "089010010001244"])
def test_malformed_gtins_are_invalid(bad: str) -> None:
    assert not gtin_is_valid(bad)


@pytest.mark.parametrize("case", V["luhn32_check_examples"])
def test_luhn32_check_char(case: dict[str, str]) -> None:
    assert luhn32_check_char(case["payload"]) == case["check"]


@pytest.mark.parametrize("serial", V["serial_valid"])
def test_valid_serials(serial: str) -> None:
    assert luhn32_is_valid(serial)


@pytest.mark.parametrize("serial", V["serial_invalid"])
def test_invalid_serials(serial: str) -> None:
    assert not luhn32_is_valid(serial)


def test_luhn32_rejects_characters_outside_alphabet() -> None:
    assert not luhn32_is_valid("TPM9S346QO7")
    with pytest.raises(ValueError):
        luhn32_check_char("TPU")
