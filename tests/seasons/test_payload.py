from dataclasses import dataclass
from datetime import datetime

from app.seasons.payload import build_season_payload, serialize_season


@dataclass
class StubSeason:
    id: int
    name: str = '2026 Fall/Winter'
    season_type: str = 'fall/winter'
    year: int = 2026
    price_cents: int | None = 20500
    returning_start: datetime | None = None
    returning_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None


NOW = datetime(2026, 7, 30, 12, 0, 0)

FALL = StubSeason(
    1,
    returning_start=datetime(2026, 8, 28, 17, 0, 0),
    returning_end=datetime(2026, 9, 2, 5, 0, 0),
    new_start=datetime(2026, 9, 3, 17, 0, 0),
    new_end=datetime(2026, 9, 20, 5, 0, 0),
)
SPRING = StubSeason(
    2,
    name='2027 Spring/Summer',
    season_type='spring/summer',
    year=2027,
    returning_start=datetime(2027, 3, 1, 17, 0, 0),
    returning_end=datetime(2027, 3, 20, 5, 0, 0),
)


def test_serializes_timestamps_with_an_explicit_utc_marker():
    body = serialize_season(FALL)
    assert body['returning_start'] == '2026-08-28T17:00:00Z'
    assert body['new_end'] == '2026-09-20T05:00:00Z'


def test_serializes_null_windows_as_null():
    body = serialize_season(SPRING)
    assert body['new_start'] is None
    assert body['new_end'] is None


def test_serializes_the_descriptive_fields():
    body = serialize_season(FALL)
    assert body['name'] == '2026 Fall/Winter'
    assert body['season_type'] == 'fall/winter'
    assert body['year'] == 2026
    assert body['price_cents'] == 20500


def test_payload_keys_one_entry_per_season_type():
    body = build_season_payload([FALL, SPRING], NOW)
    assert sorted(body['by_type']) == ['fall/winter', 'spring/summer']
    assert body['by_type']['fall/winter']['name'] == '2026 Fall/Winter'


def test_primary_is_the_soonest_across_every_type():
    body = build_season_payload([SPRING, FALL], NOW)
    assert body['primary']['season_type'] == 'fall/winter'


def test_primary_is_null_when_no_season_has_a_window():
    body = build_season_payload([StubSeason(9)], NOW)
    assert body['primary'] is None
    assert body['by_type'] == {}


def test_generated_at_marks_the_build_moment():
    body = build_season_payload([FALL], NOW)
    assert body['generated_at'] == '2026-07-30T12:00:00Z'


def test_legacy_season_types_still_appear_and_are_simply_unmatched():
    legacy = StubSeason(
        3,
        name='2019 Winter',
        season_type='legacy',
        returning_start=datetime(2019, 9, 1),
        returning_end=datetime(2019, 9, 30),
    )
    body = build_season_payload([FALL, legacy], NOW)
    assert 'legacy' in body['by_type']
    assert body['primary']['season_type'] == 'fall/winter'


def test_seasons_without_a_type_are_skipped_in_by_type():
    untyped = StubSeason(
        4,
        season_type='',
        returning_start=datetime(2026, 8, 1),
        returning_end=datetime(2026, 8, 5),
    )
    body = build_season_payload([FALL, untyped], NOW)
    assert '' not in body['by_type']
