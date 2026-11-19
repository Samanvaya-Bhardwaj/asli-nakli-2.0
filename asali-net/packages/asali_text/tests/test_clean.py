import pytest
from asali_text.clean import normalise, redact


@pytest.mark.parametrize(
    "text",
    ["call 9876543210 now", "call +91 98765 43210 now", "call 098765-43210 now", "call 91-9876543210 now"],
)
def test_indian_phone_formats_are_removed(text):
    out, found = redact(text)
    assert "[phone]" in out and "98765" not in out and found == ["phone"]


def test_email_and_long_id_are_removed():
    out, found = redact("write to a.b+c@mail.example.co.in, id 123456789012.")
    assert out == "write to [email], id [id]." and found == ["email", "id"]


def test_batch_numbers_and_prices_survive():
    text = "Batch TP24A017 costs 125.50 and expires 03/2027; strip of 10."
    assert redact(text) == (text, [])


def test_normalise_folds_width_and_whitespace():
    assert normalise("\uff34ablet \x00 smells   odd\r\n\r\n\r\n\r\nnow ") == "Tablet smells odd\n\nnow"
