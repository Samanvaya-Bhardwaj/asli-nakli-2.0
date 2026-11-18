import pytest
from asali_codes.candidates import serial_candidates
from asali_codes.read import format_serial, read

GTIN = "08901001000124"
TRUE = "TPM9S346Q37"
ISSUERS = {"TP", "MV", "KS"}
OTHER = "KS6CQ643DZ3"


def exists_only(*serials):
    allowed = set(serials)
    return lambda gtin, cands: {c for c in cands if c in allowed}


def test_format_serial_groups_4_4_3():
    assert format_serial(TRUE) == "TPM9-S346-Q37"


def test_valid_code_is_accepted():
    r = read(
        f"https://id.asali.example/01/{GTIN}/21/{TRUE}?10=TP24A017&17=270331",
        context="consumer",
        issuers=ISSUERS,
    )
    assert r.decision == "accepted"
    assert (r.gtin, r.serial, r.lot) == (GTIN, TRUE, "TP24A017")
    assert r.chosen is None


def test_staff_unique_expected_match_is_corrected():
    r = read("TPM95346Q37", context="staff", issuers=ISSUERS, expected={(GTIN, TRUE), (GTIN, OTHER)})
    assert r.decision == "corrected"
    assert r.serial == TRUE
    assert r.chosen is not None and r.chosen.cost == 0.3
    assert r.message == "Read as TPM9-5346-Q37, corrected to TPM9-S346-Q37."


def test_consumer_same_case_needs_confirmation():
    r = read("TPM95346Q37", context="consumer", issuers=ISSUERS, exists=exists_only(TRUE))
    assert r.decision == "needs_confirmation"
    assert r.serial == TRUE
    assert r.message == "Does your pack show TPM9-S346-Q37?"


def test_several_close_candidates_need_a_choice():
    near = [c.value for c in serial_candidates("TPM0S346Q37", ISSUERS) if c.cost == 1.0][:3]
    assert len(near) == 3
    r = read("TPM0S346Q37", context="staff", issuers=ISSUERS, expected={(GTIN, s) for s in near})
    assert r.decision == "needs_choice"
    assert sorted(c.value for c in r.choices) == sorted(near)
    assert r.serial is None


def test_no_candidate_is_unreadable():
    r = read("TPM0S346Q37", context="staff", issuers=ISSUERS, expected={(GTIN, OTHER)})
    assert r.decision == "unreadable"
    assert r.message == "We could not read this code. Scan again or type the code printed after SN."


@pytest.mark.parametrize("raw", ["", "hello world", "????"])
def test_garbage_is_unreadable(raw):
    assert read(raw, context="consumer", issuers=ISSUERS).decision == "unreadable"


def test_consumer_without_existence_check_and_many_candidates_is_unreadable():
    r = read("TPM0S346Q37", context="consumer", issuers=ISSUERS)
    assert r.decision == "unreadable"


def test_product_number_alone_is_not_a_pack_code():
    r = read(GTIN, context="consumer", issuers=ISSUERS)
    assert r.decision == "unreadable"
    assert "product number" in r.message


def test_gtin_off_by_one_digit_is_corrected_for_staff():
    raw = f"(01)08901001000154(21){TRUE}"
    r = read(raw, context="staff", issuers=ISSUERS, known_gtins=[GTIN, "08901001000292"])
    assert r.decision == "corrected"
    assert r.gtin == GTIN
    assert r.serial == TRUE


def test_gtin_off_by_one_digit_needs_confirmation_for_consumer():
    raw = f"(01)08901001000154(21){TRUE}"
    r = read(raw, context="consumer", issuers=ISSUERS, known_gtins=[GTIN])
    assert r.decision == "needs_confirmation"
    assert r.gtin == GTIN


def test_expected_set_is_restricted_to_the_read_gtin():
    r = read(
        f"(01){GTIN}(21)TPM95346Q37", context="staff", issuers=ISSUERS, expected={("08901001000292", TRUE)}
    )
    assert r.decision == "unreadable"
