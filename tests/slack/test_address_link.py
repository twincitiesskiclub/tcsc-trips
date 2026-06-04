"""Tests for the clickable-address helper in practice announcements."""

from urllib.parse import quote_plus

from app.practices.interfaces import PracticeLocationInfo
from app.slack.blocks.announcements import _address_link


def _loc(**kw) -> PracticeLocationInfo:
    base = dict(id=1, name="Theodore Wirth")
    base.update(kw)
    return PracticeLocationInfo(**base)


def test_uses_stored_google_maps_url_when_present():
    loc = _loc(
        address="1221 Theodore Wirth Pkwy, Minneapolis, MN 55422",
        google_maps_url="https://maps.app.goo.gl/abc123",
        latitude=44.99, longitude=-93.32,
    )
    result = _address_link(loc)
    assert result == "<https://maps.app.goo.gl/abc123|1221 Theodore Wirth Pkwy, Minneapolis, MN 55422>"


def test_falls_back_to_coords_pin_when_no_url():
    loc = _loc(
        address="1221 Theodore Wirth Pkwy, Minneapolis, MN 55422",
        google_maps_url=None,
        latitude=44.991258, longitude=-93.32639,
    )
    result = _address_link(loc)
    assert result == (
        "<https://www.google.com/maps/search/?api=1&query=44.991258,-93.32639"
        "|1221 Theodore Wirth Pkwy, Minneapolis, MN 55422>"
    )


def test_falls_back_to_address_search_when_no_url_or_coords():
    loc = _loc(address="8100 Grimm Rd", google_maps_url=None, latitude=None, longitude=None)
    result = _address_link(loc)
    assert result == (
        f"<https://www.google.com/maps/search/?api=1&query={quote_plus('8100 Grimm Rd')}"
        "|8100 Grimm Rd>"
    )


def test_returns_none_when_no_address():
    loc = _loc(address=None, google_maps_url=None, latitude=None, longitude=None)
    assert _address_link(loc) is None


def test_url_never_expands_label_is_address():
    loc = _loc(address="RJGJ+J9 Bloomington, Minnesota",
               google_maps_url=None, latitude=44.826683, longitude=-93.369113)
    result = _address_link(loc)
    assert result.endswith("|RJGJ+J9 Bloomington, Minnesota>")
    assert result.startswith("<https://www.google.com/maps/search/?api=1&query=44.826683,-93.369113")
