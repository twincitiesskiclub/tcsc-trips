import pytest

from app.utils import normalize_phone_e164


@pytest.mark.parametrize("raw,expected", [
    ("612-867-7165", "+16128677165"),          # prod's dashed format
    ("6128677165", "+16128677165"),            # bare 10 digits
    ("16129985285", "+16129985285"),           # 11 digits leading 1
    ("+17634397034", "+17634397034"),          # already E.164
    ("(612) 867-7165", "+16128677165"),        # parens and spaces
    ("612.867.7165", "+16128677165"),          # dots
    (" 612 867 7165 ", "+16128677165"),        # whitespace
])
def test_normalizes_us_formats(raw, expected):
    assert normalize_phone_e164(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "555-0100",               # 7-digit local number: rejected
    "911", "1", "123456789",                   # too short
    "612867716512", "26128677165",             # 12 digits / 11 not starting with 1
    "+447911123456",                           # non-US
    "not a phone",
])
def test_rejects_non_nanp(raw):
    assert normalize_phone_e164(raw) is None
