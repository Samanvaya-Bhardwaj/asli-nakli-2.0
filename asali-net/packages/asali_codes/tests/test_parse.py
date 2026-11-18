from datetime import date

import pytest
from asali_codes.parse import parse
from vectors import V

GTIN = "08901001000124"
SERIAL = "TPM9S346Q37"


def _expect(r, case):
    assert r.gtin == case["gtin"]
    assert r.serial == case["serial"]
    assert r.lot == case["lot"]
    assert r.expiry == date.fromisoformat(case["expiry"])
    assert r.status == {"gtin": "valid", "serial": "valid", "lot": "valid", "expiry": "valid"}


@pytest.mark.parametrize("case", V["digital_link_examples"])
def test_digital_link(case):
    r = parse(case["raw"])
    assert r.grammar == "digital_link"
    _expect(r, case)


@pytest.mark.parametrize("case", V["element_string_examples"])
def test_element_strings(case):
    r = parse(case["raw"])
    assert r.grammar == "element_string"
    _expect(r, case)


def test_digital_link_with_lot_as_path_qualifier():
    r = parse(f"https://id.asali.example/01/{GTIN}/10/TP24A017/21/{SERIAL}?17=270331")
    assert (r.gtin, r.lot, r.serial, r.expiry) == (GTIN, "TP24A017", SERIAL, date(2027, 3, 31))


def test_element_string_without_gs_where_lot_contains_21():
    raw = f"01{GTIN}17270331" + "10TP21A017" + f"21{SERIAL}"
    r = parse(raw)
    assert r.lot == "TP21A017"
    assert r.serial == SERIAL


def test_expiry_day_00_means_last_day_of_month():
    r = parse(f"(01){GTIN}(17)270200(10)X1(21){SERIAL}")
    assert r.expiry == date(2027, 2, 28)


def test_label_line_any_order():
    r = parse(f"LOT TP24A017 EXP 03/2027 SN TPM9-S346-Q37 GTIN {GTIN}")
    assert r.grammar == "label_line"
    assert (r.gtin, r.serial, r.lot, r.expiry) == (GTIN, SERIAL, "TP24A017", date(2027, 3, 31))


@pytest.mark.parametrize(
    "line",
    [
        "B.No. K/24/0091  S/N KS6C-Q643-DZ3  Exp. MAR 2027",
        "Batch No: K/24/0091 Serial: KS6CQ643DZ3 Expiry 03/27",
    ],
)
def test_label_line_variants(line):
    r = parse(line)
    assert r.grammar == "label_line"
    assert r.lot == "K/24/0091"
    assert r.serial == "KS6CQ643DZ3"
    assert r.expiry == date(2027, 3, 31)
    assert r.status["gtin"] == "missing"


def test_bare_serial_with_hyphens():
    r = parse("tpm9-s346-q37")
    assert r.grammar == "bare_serial"
    assert r.serial == SERIAL
    assert r.status["serial"] == "valid"


def test_bare_serial_with_wrong_check_char():
    r = parse("TPM0S346Q37")
    assert r.grammar == "bare_serial"
    assert r.status["serial"] == "invalid_check"


def test_bare_gtin():
    r = parse(GTIN)
    assert r.grammar == "bare_gtin"
    assert r.gtin == GTIN
    assert r.status["serial"] == "missing"


def test_gtin_with_wrong_check_digit():
    r = parse("08901001000125")
    assert r.status["gtin"] == "invalid_check"


def test_serial_with_letter_u_is_invalid_char():
    r = parse("TPU9S346Q37")
    assert r.status["serial"] == "invalid_char"


@pytest.mark.parametrize("raw", ["", "hello world", "!!!", "12345"])
def test_garbage_is_unknown(raw):
    r = parse(raw)
    assert r.grammar == "unknown"
    assert r.serial is None and r.gtin is None
