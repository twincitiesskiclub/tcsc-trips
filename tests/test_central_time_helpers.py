"""Admins type Central wall time; the database stores naive UTC."""
from datetime import datetime

from app.utils import central_naive_to_utc_naive, utc_naive_to_central_naive


def test_cdt_value_gains_five_hours():
    assert central_naive_to_utc_naive(datetime(2026, 10, 24, 9, 0)) == datetime(2026, 10, 24, 14, 0)


def test_cst_value_gains_six_hours():
    assert central_naive_to_utc_naive(datetime(2026, 1, 19, 12, 0)) == datetime(2026, 1, 19, 18, 0)


def test_late_evening_crosses_into_the_next_utc_day():
    assert central_naive_to_utc_naive(datetime(2026, 10, 22, 23, 59)) == datetime(2026, 10, 23, 4, 59)


def test_none_passes_through():
    assert central_naive_to_utc_naive(None) is None


def test_round_trips_with_the_existing_inverse():
    value = datetime(2026, 3, 9, 7, 30)
    assert utc_naive_to_central_naive(central_naive_to_utc_naive(value)) == value
