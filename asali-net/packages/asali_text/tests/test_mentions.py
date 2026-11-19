import pytest
from asali_text.gazetteer import Gazetteer, ProductName
from asali_text.language import language_of
from asali_text.mentions import by_kind, extract

GAZ = Gazetteer(
    products=(
        ProductName("08901001000049", "Amoxitar", "amoxicillin", "500 mg"),
        ProductName("08901003000111", "Glargikes", "insulin glargine", "100 IU/ml"),
    ),
    orgs={
        "shop-delhi": "Sharma Medicos",
        "shop-mumbai": "Apna Chemist",
        "dist-north": "North Star Distributors",
    },
)
SERIAL = "TPM9S346Q37"


def one(text, kind):
    found = by_kind(extract(text, GAZ), kind)
    assert len(found) == 1, found
    return found[0]


def test_serial_with_hyphens_lowercase_and_misreads():
    plain = one(f"Code {SERIAL} on the strip", "serial")
    assert (plain.value, plain.valid, plain.text) == (SERIAL, True, SERIAL)
    assert one("code TPM9-S346-Q37.", "serial").value == SERIAL
    low = one("code tpm9 s346 q37", "serial")
    assert low.value == SERIAL and low.valid
    wrong = one(
        "code TPM9-S346-Q3I", "serial"
    )  # an I is read as a 1: a different, invalid code that linking may correct
    assert wrong.value == "TPM9S346Q31" and wrong.valid is False
    broken = one("code TPM9-S346-Q38", "serial")
    assert broken.valid is False  # kept, flagged invalid, so linking may correct it


def test_the_span_points_at_the_text():
    text = "Maine liya. Code TPM9-S346-Q37 hai."
    m = one(text, "serial")
    assert text[m.start : m.end] == "TPM9-S346-Q37"


@pytest.mark.parametrize(
    "text, value",
    [
        ("Batch TP24A017 was fine", "TP24A017"),
        ("batch tp 24a0l7", "TP24A017"),
        ("lot MV-2410-033", "MV-2410-033"),
        ("lot mv 2410 033", "MV-2410-033"),
        ("B.No. K/24/0091 failed", "K/24/0091"),
        ("k - 24 - 0O91", "K/24/0091"),
    ],
)
def test_lot_grammars_and_relaxed_variants(text, value):
    assert one(text, "lot").value == value


def test_shipment_refs_and_gtin():
    assert one("Shipment DSP-N-0042 left", "shipment_ref").value == "DSP-N-0042"
    assert one("ref shp-ab12cd34ef ok", "shipment_ref").value == "SHP-AB12CD34EF"
    assert one("GTIN 08901001000049", "gtin").value == "08901001000049"
    assert one("GTIN 8901001000049", "gtin").value == "08901001000049"  # a leading zero lost


def test_product_org_and_city_names_with_typos_and_variants():
    p = one("I bought Amoxitar tablets", "product")
    assert p.value["gtin"] == "08901001000049"
    assert one("bought amoxitr strip", "product").value["gtin"] == "08901001000049"
    assert one("generic insulin glargine pen", "product").value["gtin"] == "08901003000111"
    assert one("from sharma medical in lajpat nagar", "org").value["org_id"] == "shop-delhi"
    assert one("at apna chemists andheri", "org").value["org_id"] == "shop-mumbai"
    assert one("bought in Bombay", "city").value == "Mumbai"
    assert one("shop in Bangalore", "city").value == "Bengaluru"


def test_dates_in_many_formats():
    assert one("on 12/11/2026 I", "date").value == "2026-11-12"
    assert one("on 12-11-26 I", "date").value == "2026-11-12"
    assert one("on 3 Nov ko liya", "date").value == "2026-11-03"
    assert one("12/11 09:10  6.1 C", "date").value == "2026-11-12"
    assert one("31/02/2026 is not a date", "date").value is None


def test_expiry_temperature_duration_strength():
    assert one("expiry 08/2026 printed", "expiry").value == "2026-08"
    assert one("exp: Mar 2027", "expiry").value == "2027-03"
    assert one("read 14.2 C at noon", "temperature").value == 14.2
    assert one("read 14.2 °C at noon", "temperature").value == 14.2
    assert one("above 8 C for about 3 h 20 min", "duration").value == 200
    assert one("3 ghante tak", "duration").value == 180
    assert one("Amoxitar 500 mg", "strength").value == "500 mg"


def test_ordinary_words_are_not_codes():
    found = extract("The tablets were fine and the shop was clean on a Monday", GAZ)
    assert [m.kind for m in found] == []


def test_hinglish_is_told_from_english():
    assert (
        language_of("Maine 3 Nov ko dawai li, strip ka colour alag hai aur koi fayda nahi hua") == "hi-Latn"
    )
    assert language_of("The strip colour is different and the tablets did not help") == "en"
