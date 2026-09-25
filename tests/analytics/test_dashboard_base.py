from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from werkzeug.datastructures import MultiDict

from app.analytics.dashboards import base
from app.analytics.models import PracticeSession, PracticeAttendance, SlackArchiveMessage
from app.practices.models import PracticeLocation

from app.analytics.dashboards.base import Dashboard, parse_filters

DOMAINS = {"seasons": {"2025 Fall/Winter", "2026 Spring/Summer"}, "activities": {"Strength", "Run"},
           "workout_types": {"Circuit"}, "location_ids": {38}}
D = Dashboard(slug="t", title="T", question="Q?",
              filters=["season", "date_range", "day_of_week", "format"],
              build=lambda f: [], fixed={"activities": ["Strength"]}, defaults={"days": ["Thursday"]})


def _parse(**args):
    with patch("app.analytics.dashboards.base.get_filter_domains", return_value=DOMAINS):
        return parse_filters(MultiDict(args), D)


def test_invalid_values_dropped_and_defaults_applied():
    f = _parse(season=["2025 Fall/Winter", "<script>"], date_from="notadate", format=["split", "bogus"])
    assert f.seasons == ["2025 Fall/Winter"] and f.date_from is None and f.formats == ["split"]
    assert f.days == ["Thursday"] and f.activities == ["Strength"] and f.kinds == ["practice"]


def test_request_overrides_defaults_but_not_fixed():
    f = _parse(day_of_week=["Wednesday", "Friday"], activity=["Run"], date_from="2025-05-01")
    assert f.days == ["Wednesday", "Friday"] and f.activities == ["Strength"]
    assert f.date_from == date(2025, 5, 1)


def test_all_filters_validate_and_disallowed_requests_are_ignored():
    dashboard = Dashboard('all', 'All', '?', list(base.FILTER_NAMES), lambda f: [])
    args = MultiDict({'activity': ['Run', 'junk'], 'workout_type': ['Circuit', 'junk'],
                      'location': ['38', '999', 'no'], 'kind': ['event', 'junk'],
                      'date_to': '2025-06-01', 'day_of_week': ['Monday', 'junk']})
    with patch.object(base, 'get_filter_domains', return_value=DOMAINS):
        f = parse_filters(args, dashboard)
        ignored = parse_filters(args, Dashboard('none', 'None', '?', [], lambda f: []))
    assert f.activities == ['Run'] and f.workout_types == ['Circuit']
    assert f.location_ids == [38] and f.kinds == ['event'] and f.days == ['Monday']
    assert f.date_to == date(2025, 6, 1)
    assert ignored.activities == [] and ignored.location_ids == [] and ignored.kinds == ['practice']
    assert ignored.date_to is None


def test_empty_and_invalid_requests_use_defaults():
    assert _parse(day_of_week=['junk', '']).days == ['Thursday']


def test_dashboard_mutable_defaults_are_independent():
    first = Dashboard('a', 'A', '?', [], lambda f: [])
    second = Dashboard('b', 'B', '?', [], lambda f: [])
    first.fixed['activities'] = ['Run']
    first.defaults['days'] = ['Monday']
    assert not second.fixed and not second.defaults


def _session(key, day, **values):
    return PracticeSession(session_key='task13:' + key, group_key='task13:' + key,
                           era='app', date=day, day_of_week=day.strftime('%A'),
                           season_label='2099 Test', rebuilt_at=datetime(2099, 1, 1), **values)


def test_load_sessions_and_options_exclude_future_central_dates(db_session):
    today = date(2099, 1, 5)
    earlier = _session('earlier', today - timedelta(days=1), start_time=time(18), activity='Past activity')
    first = _session('first', today, start_time=time(6), activity='Past activity')
    second = _session('second', today, start_time=time(18), activity='Past activity')
    future = _session('future', today + timedelta(days=1), activity='Future only', workout_type='Future workout', format='merged')
    future.season_label = '2100 Future'
    db_session.add_all([second, future, first, earlier])
    db_session.flush()
    with patch('app.utils.today_central', return_value=today):
        sessions = base.load_sessions(base.Filters(seasons=['2099 Test', '2100 Future']))
        options = base.filter_options(D)
        domains = base.get_filter_domains()
    assert [s.id for s in sessions] == [earlier.id, first.id, second.id]
    assert '2100 Future' not in options['seasons']
    assert 'Future only' not in options['activities'] and 'Future workout' not in options['workout_types']
    assert 'Future only' not in domains['activities']


def test_apply_every_filter_and_attendance_role(db_session):
    matching = _session('matching', date(2099, 1, 5), activity='Strength', workout_type='Circuit', format='split')
    excluded = _session('excluded', date(2099, 1, 6), activity='Run', kind='event')
    db_session.add_all([matching, excluded])
    db_session.flush()
    rsvp = PracticeAttendance(session_id=matching.id, slack_uid='UFAKE1301', role='rsvp', source='app')
    lead = PracticeAttendance(session_id=matching.id, slack_uid='UFAKE1302', role='lead', source='app')
    other = PracticeAttendance(session_id=excluded.id, slack_uid='UFAKE1303', role='rsvp', source='app')
    db_session.add_all([rsvp, lead, other])
    db_session.flush()
    f = base.Filters(seasons=['2099 Test'], date_from=date(2099, 1, 5), date_to=date(2099, 1, 5),
                     days=['Monday'], activities=['Strength'], workout_types=['Circuit'], formats=['split'])
    assert base.apply_filters(PracticeSession.query, f).all() == [matching]
    rows = base.load_attendance([matching.id])
    assert [(r.session_id, r.slack_uid, r.slot, r.role) for r in rows] == [(matching.id, 'UFAKE1301', None, 'rsvp')]
    assert tuple(rows[0]._mapping) == ('session_id', 'slack_uid', 'slot', 'role')
    assert [r.slack_uid for r in base.load_attendance([matching.id], role='lead')] == ['UFAKE1302']
    assert base.load_attendance([]) == []


def test_footer_uses_latest_sync_not_post_date_and_central_timezone(db_session):
    before = base.footer()['needs_review']
    message = SlackArchiveMessage(channel_id='CFAKE13', ts='1300000000.001',
                                  posted_at=datetime(2090, 1, 1), synced_at=datetime(2099, 1, 6, 2), raw={})
    flagged = _session('review', date(2099, 1, 5), needs_review=True)
    db_session.add_all([message, flagged])
    db_session.flush()
    footer = base.footer()
    assert footer['data_through'] == 'Jan 05, 2099 08:00 PM CST'
    assert footer['needs_review'] == before + 1


@pytest.mark.parametrize('attribute, selected', [
    ('seasons', ['2099 Test']), ('days', ['Monday']), ('activities', ['Strength']),
    ('workout_types', ['Circuit']), ('formats', ['split']), ('kinds', ['practice']),
    ('date_from', date(2099, 1, 5)), ('date_to', date(2099, 1, 5)),
])
def test_each_filter_changes_the_query(db_session, attribute, selected):
    matching = _session('selected', date(2099, 1, 5), activity='Strength', workout_type='Circuit', format='split')
    other_day = date(2099, 1, 4) if attribute == 'date_from' else date(2099, 1, 6)
    excluded = _session('not-selected', other_day, activity='Run', workout_type='Other', format='single', kind='event')
    excluded.season_label = '2098 Test'
    db_session.add_all([matching, excluded])
    db_session.flush()
    filters = base.Filters(kinds=[])
    setattr(filters, attribute, selected)
    query = PracticeSession.query.filter(PracticeSession.id.in_([matching.id, excluded.id]))
    assert base.apply_filters(query, filters).all() == [matching]


def test_location_filters_and_past_options_ordering(db_session):
    past_location = PracticeLocation(name='Task 13 past', created_at=datetime(2099, 1, 1), updated_at=datetime(2099, 1, 1))
    future_location = PracticeLocation(name='Task 13 future', created_at=datetime(2099, 1, 1), updated_at=datetime(2099, 1, 1))
    db_session.add_all([past_location, future_location])
    db_session.flush()
    spring = _session('spring', date(2099, 1, 4), location_id=past_location.id, location_name=past_location.name)
    spring.season_label = '2099 Spring/Summer'
    fall = _session('fall', date(2099, 1, 5))
    fall.season_label = '2099 Fall/Winter'
    future = _session('future-location', date(2099, 1, 6), location_id=future_location.id, location_name=future_location.name, format='merged')
    db_session.add_all([spring, fall, future])
    db_session.flush()
    with patch('app.utils.today_central', return_value=date(2099, 1, 5)):
        options = base.filter_options(D)
        assert base.load_sessions(base.Filters(location_ids=[past_location.id])) == [spring]
        assert future_location.id not in base.get_filter_domains()['location_ids']
    assert (past_location.id, past_location.name) in options['locations']
    assert (future_location.id, future_location.name) not in options['locations']
    seasons = [s for s in options['seasons'] if s.startswith('2099')]
    assert seasons == ['2099 Fall/Winter', '2099 Spring/Summer']
    assert options['days'].index('Monday') < options['days'].index('Sunday')


@pytest.mark.parametrize('attribute, fixed', [
    ('seasons', ['2099 Absent']), ('activities', ['Absent activity']),
    ('workout_types', ['Absent workout']), ('location_ids', ['999999']),
])
def test_fixed_database_values_survive_missing_domains(attribute, fixed):
    dashboard = Dashboard('fixed', 'Fixed', '?', [], lambda f: [], fixed={attribute: fixed})
    with patch.object(base, 'get_filter_domains', return_value=DOMAINS):
        filters = parse_filters(MultiDict(), dashboard)
    assert getattr(filters, attribute) == ([999999] if attribute == 'location_ids' else fixed)


def test_absent_fixed_activity_returns_no_sessions_instead_of_other_activities(db_session):
    session = _session('fixed-other', date(2099, 1, 5), activity='Run')
    db_session.add(session)
    db_session.flush()
    dashboard = Dashboard('fixed', 'Fixed', '?', ['activity'], lambda f: [],
                          fixed={'activities': ['Strength']})
    domains = {**DOMAINS, 'activities': {'Run'}}
    with patch.object(base, 'get_filter_domains', return_value=domains):
        filters = parse_filters(MultiDict({'activity': 'Run'}), dashboard)
    assert filters.activities == ['Strength']
    query = PracticeSession.query.filter(PracticeSession.id == session.id)
    assert base.apply_filters(query, filters).all() == []


def test_fixed_values_still_validate_catalogs_and_coerce_locations():
    dashboard = Dashboard('fixed', 'Fixed', '?', [], lambda f: [], fixed={
        'days': ['Monday', 'invalid'], 'formats': ['split', 'invalid'],
        'kinds': ['event', 'invalid'], 'location_ids': ['999999', 'invalid'],
        'activity': 'Absent activity',
    })
    with patch.object(base, 'get_filter_domains', return_value=DOMAINS):
        filters = parse_filters(MultiDict(), dashboard)
    assert filters.days == ['Monday'] and filters.formats == ['split'] and filters.kinds == ['event']
    assert filters.location_ids == [999999] and filters.activities == ['Absent activity']


@pytest.mark.parametrize("source", ["defaults", "fixed"])
def test_date_objects_in_dashboard_configuration(source):
    dashboard = Dashboard('dates', 'Dates', '?', ['date_range'], lambda f: [],
                          **{source: {'date_from': date(2099, 5, 1), 'date_to': date(2099, 9, 1)}})
    with patch.object(base, 'get_filter_domains', return_value=DOMAINS):
        filters = parse_filters(MultiDict(), dashboard)
    assert filters.date_from == date(2099, 5, 1)
    assert filters.date_to == date(2099, 9, 1)
