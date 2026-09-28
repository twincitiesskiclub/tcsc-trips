from datetime import date

import pytest

from app.analytics.drafts import SeasonRef
from app.analytics.seasons import (
    season_in_progress, season_key, season_label, shift_season, short_season_label,
)

SEASONS = [SeasonRef("2025 Fall/Winter", date(2025, 9, 11), date(2026, 3, 19))]


def test_uses_seasons_table_when_date_inside():
    assert season_label(date(2025, 12, 3), SEASONS) == "2025 Fall/Winter"


def test_computed_label_for_winter_months():
    assert season_label(date(2023, 1, 31), []) == "2022 Fall/Winter"
    assert season_label(date(2022, 10, 25), []) == "2022 Fall/Winter"
    assert season_label(date(2024, 4, 2), []) == "2023 Fall/Winter"


def test_computed_label_for_summer_months():
    assert season_label(date(2023, 6, 13), []) == "2023 Spring/Summer"
    assert season_label(date(2025, 9, 5), []) == "2025 Fall/Winter"  # Sep counts as Fall/Winter


def test_gap_between_table_seasons_falls_back_to_rule():
    # 2025-09-05 is before the 2025 Fall/Winter season starts on 9/11
    assert season_label(date(2025, 9, 5), SEASONS) == "2025 Fall/Winter"


def test_season_key_orders_labels():
    assert sorted(["2099 Fall/Winter", "2099 Spring/Summer", "2098 Fall/Winter"], key=season_key) == [
        "2098 Fall/Winter", "2099 Spring/Summer", "2099 Fall/Winter"]
    assert season_key("Unknown") == (0, 0)


@pytest.mark.parametrize("label, today, expected", [
    ("2099 Spring/Summer", date(2099, 4, 30), False),
    ("2099 Spring/Summer", date(2099, 5, 1), True),
    ("2099 Spring/Summer", date(2099, 8, 31), True),
    ("2099 Spring/Summer", date(2099, 9, 1), False),
    ("2099 Fall/Winter", date(2099, 8, 31), False),
    ("2099 Fall/Winter", date(2099, 9, 1), True),
    ("2099 Fall/Winter", date(2100, 4, 30), True),
    ("2099 Fall/Winter", date(2100, 5, 1), False),
    ("Unknown", date(2099, 6, 1), False),
    ("2099 Unknown", date(2099, 6, 1), False),
    ("0000 Spring/Summer", date(2099, 6, 1), False),
    (None, date(2099, 6, 1), False),
])
def test_season_in_progress_boundaries(label, today, expected):
    assert season_in_progress(label, today) is expected


def test_shift_keeps_season_type_across_years():
    assert shift_season("2099 Spring/Summer", 1) == "2100 Spring/Summer"
    assert shift_season("2099 Fall/Winter", -1) == "2098 Fall/Winter"


@pytest.mark.parametrize("label, short", [("2025 Fall/Winter", "Fall 25"),
    ("2026 Spring/Summer", "Sum 26"), ("2099 Fall/Winter", "Fall 99"),
    ("Custom season", "Custom season")])
def test_short_season_label(label, short):
    assert short_season_label(label) == short
