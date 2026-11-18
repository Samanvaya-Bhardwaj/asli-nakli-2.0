import time

from asali_codes.candidates import gtin_candidates, serial_candidates
from asali_codes.checks import luhn32_is_valid
from asali_codes.confusion import substitution_cost, weighted_distance

ISSUERS = {"TP", "MV", "KS"}
TRUE = "TPM9S346Q37"


def values(cands):
    return [c.value for c in cands]


def cost_of(cands, value):
    return next(c.cost for c in cands if c.value == value)


def test_confusion_costs_are_symmetric_and_cheaper_for_lookalikes():
    assert substitution_cost("S", "5") == substitution_cost("5", "S") == 0.3
    assert substitution_cost("8", "B") == 0.3
    assert substitution_cost("X", "4") == 1.0
    assert substitution_cost("A", "A") == 0.0


def test_weighted_distance():
    assert weighted_distance(TRUE, TRUE) == 0.0
    assert weighted_distance(TRUE, "TPM95346Q37") == 0.3
    assert weighted_distance(TRUE, "TPM9S364Q37") == 0.6
    assert weighted_distance(TRUE, "TPM99S346Q37") == 0.5
    assert weighted_distance(TRUE, "TPMS346Q37") == 1.0


def test_wrong_character_recovered_through_check_char():
    cands = serial_candidates("TPM0S346Q37", ISSUERS)
    assert TRUE in values(cands)
    assert cost_of(cands, TRUE) == 1.0


def test_lookalike_substitution_is_cheap():
    cands = serial_candidates("TPM95346Q37", ISSUERS)
    assert cands[0].value == TRUE
    assert cands[0].cost == 0.3


def test_adjacent_swap_costs_06():
    cands = serial_candidates("TPM9S364Q37", ISSUERS)
    assert cost_of(cands, TRUE) == 0.6


def test_doubled_and_missing_characters():
    assert cost_of(serial_candidates("TPM99S346Q37", ISSUERS), TRUE) == 0.5
    assert cost_of(serial_candidates("TPMS346Q37", ISSUERS), TRUE) == 1.0


def test_letter_u_can_be_read_as_v():
    cands = serial_candidates("MUV37E3S3EW", ISSUERS)
    assert "MVV37E3S3EW" in values(cands)


def test_every_candidate_is_valid_sorted_and_limited():
    cands = serial_candidates("TPM0S346Q37", ISSUERS, limit=15)
    assert 0 < len(cands) <= 15
    assert all(luhn32_is_valid(c.value) and c.value[:2] in ISSUERS for c in cands)
    assert [c.cost for c in cands] == sorted(c.cost for c in cands)
    assert len(set(values(cands))) == len(cands)


def test_unknown_issuer_is_filtered_out():
    assert serial_candidates("ZZM0S346Q37", ISSUERS) == [] or all(
        c.value[:2] in ISSUERS for c in serial_candidates("ZZM0S346Q37", ISSUERS)
    )


def test_candidate_search_is_fast():
    start = time.perf_counter()
    serial_candidates("TPM0S3A6Q37", ISSUERS)
    assert time.perf_counter() - start < 1.0


def test_gtin_candidates_from_known_set():
    known = ["08901001000124", "08901001000292", "08901002001045"]
    cands = gtin_candidates("08901001000154", known)
    assert cands[0].value == "08901001000124"
    assert gtin_candidates("08901001000154", []) == []
    assert gtin_candidates("99999999999999", known) == []
