from datetime import date

from app.analytics.drafts import SeasonRef
from app.analytics.seasons import season_label

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
