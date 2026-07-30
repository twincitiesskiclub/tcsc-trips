"""The selection rule is pure: it takes any object with the four window
columns, so these tests use a stub rather than the ORM model or a database."""
from dataclasses import dataclass
from datetime import datetime

from app.seasons.selection import select_season, span_end, span_start


@dataclass
class StubSeason:
    id: int
    returning_start: datetime | None = None
    returning_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None


NOW = datetime(2026, 7, 30, 12, 0, 0)


def _season(id, r_start=None, r_end=None, n_start=None, n_end=None):
    return StubSeason(id, r_start, r_end, n_start, n_end)


def test_span_start_is_the_earliest_window_open():
    season = _season(
        1,
        r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2),
        n_start=datetime(2026, 9, 3), n_end=datetime(2026, 9, 20),
    )
    assert span_start(season) == datetime(2026, 8, 28)
    assert span_end(season) == datetime(2026, 9, 20)


def test_span_ignores_null_windows():
    season = _season(1, n_start=datetime(2026, 9, 3), n_end=datetime(2026, 9, 20))
    assert span_start(season) == datetime(2026, 9, 3)
    assert span_end(season) == datetime(2026, 9, 20)


def test_span_is_none_when_no_windows_exist():
    assert span_start(_season(1)) is None
    assert span_end(_season(1)) is None


def test_prefers_the_season_open_right_now():
    open_now = _season(1, r_start=datetime(2026, 7, 1), r_end=datetime(2026, 8, 1))
    upcoming = _season(2, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([upcoming, open_now], NOW) is open_now


def test_falls_to_the_soonest_upcoming_when_none_are_open():
    soon = _season(1, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    later = _season(2, r_start=datetime(2027, 8, 28), r_end=datetime(2027, 9, 2))
    assert select_season([later, soon], NOW) is soon


def test_falls_to_the_most_recently_ended_when_all_are_past():
    old = _season(1, r_start=datetime(2024, 8, 28), r_end=datetime(2024, 9, 2))
    recent = _season(2, r_start=datetime(2025, 8, 28), r_end=datetime(2025, 9, 2))
    assert select_season([old, recent], NOW) is recent


def test_ignores_seasons_with_no_windows_at_all():
    windowless = _season(1)
    real = _season(2, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([windowless, real], NOW) is real


def test_returns_none_when_nothing_has_a_window():
    assert select_season([_season(1), _season(2)], NOW) is None


def test_returns_none_for_an_empty_list():
    assert select_season([], NOW) is None


def test_ties_break_on_id_so_the_result_is_deterministic():
    a = _season(7, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    b = _season(3, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([a, b], NOW) is b
    assert select_season([b, a], NOW) is b
