from datetime import date
from urllib.parse import quote

from asali_codes.alphabet import ALPHABET
from asali_codes.checks import gs1_check_digit, luhn32_check_char, luhn32_is_valid
from asali_codes.confusion import SERIAL_PARTNERS
from asali_codes.parse import parse
from asali_codes.read import read
from hypothesis import given, settings
from hypothesis import strategies as st

ISSUERS = ["TP", "MV", "KS"]


@st.composite
def serials(draw: st.DrawFn) -> str:
    payload = draw(st.sampled_from(ISSUERS)) + draw(st.text(alphabet=ALPHABET, min_size=8, max_size=8))
    return payload + luhn32_check_char(payload)


@st.composite
def gtins(draw: st.DrawFn) -> str:
    body = (
        "0"
        + draw(st.sampled_from(["8901001", "8901002", "8901003"]))
        + draw(st.text(alphabet="0123456789", min_size=5, max_size=5))
    )
    return body + gs1_check_digit(body)


@given(serials(), st.integers(min_value=0, max_value=10), st.sampled_from(ALPHABET))
def test_every_single_substitution_is_detected(serial: str, pos: int, ch: str) -> None:
    if serial[pos] == ch:
        return
    assert not luhn32_is_valid(serial[:pos] + ch + serial[pos + 1 :])


@given(serials(), gtins(), st.data())
@settings(max_examples=200)
def test_one_lookalike_misread_is_corrected_for_staff(serial: str, gtin: str, data: st.DataObject) -> None:
    positions = [i for i, ch in enumerate(serial) if SERIAL_PARTNERS.get(ch)]
    if not positions:
        return
    pos = data.draw(st.sampled_from(positions))
    partner, _ = data.draw(st.sampled_from(SERIAL_PARTNERS[serial[pos]]))
    seen = serial[:pos] + partner + serial[pos + 1 :]
    r = read(f"(01){gtin}(21){seen}", context="staff", issuers=ISSUERS, expected={(gtin, serial)})
    assert r.decision == "corrected"
    assert r.serial == serial
    assert r.gtin == gtin


@given(
    gtins(),
    serials(),
    st.text(alphabet="ABCDEFGHJKMNPQRSTVWXYZ0123456789-/", min_size=1, max_size=12),
    st.dates(min_value=date(2026, 1, 1), max_value=date(2035, 12, 31)),
)
def test_digital_link_round_trip(gtin: str, serial: str, lot: str, expiry: date) -> None:
    url = (
        f"https://id.asali.example/01/{gtin}/21/{serial}"
        f"?10={quote(lot, safe='')}&17={expiry.strftime('%y%m%d')}"
    )
    r = parse(url)
    assert (r.gtin, r.serial, r.lot, r.expiry) == (gtin, serial, lot, expiry)
    assert r.status == {"gtin": "valid", "serial": "valid", "lot": "valid", "expiry": "valid"}
