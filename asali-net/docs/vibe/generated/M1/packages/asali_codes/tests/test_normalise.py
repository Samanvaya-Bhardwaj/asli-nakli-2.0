import pytest
from asali_codes.normalise import GS, normalise_raw, normalise_serial
from vectors import V


@pytest.mark.parametrize("case", V["normalize_examples"])
def test_serial_examples(case: dict[str, str]) -> None:
    serial, _ = normalise_serial(normalise_raw(case["raw"]))
    assert serial == case["serial"]


@pytest.mark.parametrize("prefix", ["]Q1", "]Q3", "]d2", "]C1"])
def test_symbology_prefix_is_stripped(prefix: str) -> None:
    assert normalise_raw(prefix + "https://id.asali.example/01/x") == "https://id.asali.example/01/x"


def test_group_separator_is_kept_and_other_controls_dropped() -> None:
    assert normalise_raw("0108901001000124\x1d21AB\r\n") == "0108901001000124" + GS + "21AB"


def test_fullwidth_characters_become_ascii() -> None:
    assert normalise_raw("ＴＰＭ９") == "TPM9"


def test_alias_letters_map_to_digits_with_a_note() -> None:
    serial, notes = normalise_serial("TPM9S346QO7")
    assert serial == "TPM9S346Q07"
    assert any("O" in n and "0" in n for n in notes)
    serial, _ = normalise_serial("tpl9-s346-qi7")
    assert serial == "TP19S346Q17"


def test_letter_u_is_reported_not_guessed() -> None:
    serial, notes = normalise_serial("TPU9S346Q37")
    assert serial == "TPU9S346Q37"
    assert any("U" in n for n in notes)


def test_accented_letter_is_reported_not_silently_changed() -> None:
    serial, notes = normalise_serial(normalise_raw("ŤPM9S346Q37"))
    assert serial != "TPM9S346Q37"
    assert any("not in the code alphabet" in n for n in notes)


def test_unicode_dashes_and_spaces_are_removed() -> None:
    serial, _ = normalise_serial("TPM9 – S346 — Q37")
    assert serial == "TPM9S346Q37"
