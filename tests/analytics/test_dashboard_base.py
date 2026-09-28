from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from werkzeug.datastructures import MultiDict

from app.analytics import SYNC_CHANNELS
from app.analytics.dashboards import base
from app.analytics.models import PracticeSession, PracticeAttendance, SlackArchiveMessage
from app.models import AppConfig
from app.practices.models import PracticeLocation

from app.analytics.dashboards.base import Dashboard, parse_filters

DOMAINS = {"seasons": {"2025 Fall/Winter", "2026 Spring/Summer"}, "activities": {"Strength", "Run"},
           "workout_types": {"Circuit"}, "location_ids": {38}}
D = Dashboard(slug="t", title="T", question="Q?",
              filters=["season", "date_range", "day_of_week", "format"],
              build=lambda f: [])


def _parse(**args):
    with patch("app.analytics.dashboards.base.get_filter_domains", return_value=DOMAINS):
        return parse_filters(MultiDict(args), D)


def test_invalid_values_dropped():
    f = _parse(season=["2025 Fall/Winter", "<script>"], date_from="notadate", format=["split", "bogus"],
               day_of_week=["junk", ""], date_to="2025-05-01")
    assert f.seasons == ["2025 Fall/Winter"] and f.date_from is None and f.formats == ["split"]
    assert f.days == [] and f.activities == [] and f.kinds == []
    assert f.date_to == date(2025, 5, 1)


def test_kinds_default_is_all():
    dashboard = Dashboard("k", "K", "?", ["kind"], lambda f: [])
    assert parse_filters(MultiDict(), dashboard, DOMAINS).kinds == []


def test_all_filters_validate_and_disallowed_requests_are_ignored():
    dashboard = Dashboard('all', 'All', '?', ['season', 'date_range', 'day_of_week', 'activity', 'workout_type', 'location', 'format', 'kind'], lambda f: [])
    args = MultiDict({'activity': ['Run', 'junk'], 'workout_type': ['Circuit', 'junk'],
                      'location': ['38', '999', 'no'], 'kind': ['event', 'trip', 'junk'],
                      'date_to': '2025-06-01', 'day_of_week': ['Monday', 'junk']})
    with patch.object(base, 'get_filter_domains', return_value=DOMAINS):
        f = parse_filters(args, dashboard)
        ignored = parse_filters(args, Dashboard('none', 'None', '?', [], lambda f: []))
    assert f.activities == ['Run'] and f.workout_types == ['Circuit']
    assert f.location_ids == [38] and f.kinds == ['event', 'trip'] and f.days == ['Monday']
    assert f.date_to == date(2025, 6, 1)
    assert ignored.activities == [] and ignored.location_ids == [] and ignored.kinds == []
    assert ignored.date_to is None


def _option_values(dashboard):
    return {attribute: [value for value, _ in pairs] for attribute, pairs in base.filter_options(dashboard).items()}


def _session(key, day, **values):
    return PracticeSession(session_key='task13:' + key, group_key='task13:' + key,
                           era='app', date=day, day_of_week=day.strftime('%A'),
                           season_label='2099 Test', rebuilt_at=datetime(2099, 1, 1), **values)


def test_missing_date_trips_are_hidden(db_session):
    today = date(2099, 1, 5)
    undated = _session("undated", today - timedelta(days=3), kind="trip", category="trip",
                       flags=["missing_date"])
    dated = _session("dated", today - timedelta(days=2), kind="trip", category="trip")
    db_session.add_all([undated, dated])
    db_session.flush()
    with patch("app.utils.today_central", return_value=today):
        keys = [s.session_key for s in base.load_sessions(base.Filters(seasons=["2099 Test"]))]
    assert "task13:dated" in keys and "task13:undated" not in keys


def test_kind_options_only_include_dated_past_sessions(db_session):
    today = date(2099, 1, 5)
    db_session.add_all([
        _session('social', today, kind='event', category='social', format='split'),
        _session('practice', today, category='practice'),
        _session('future-trip', today + timedelta(days=1), kind='trip', category='trip'),
        _session('undated-trip', today, kind='trip', category='trip', flags=['missing_date']),
    ])
    db_session.flush()
    with patch('app.utils.today_central', return_value=today):
        options = base.filter_options(D)
    assert options['kinds'] == [('practice', 'practice'), ('event', 'event')]
    assert options['formats'] == [('single', 'One session'), ('split', 'Two sessions')]


def test_practices_dashboard_limits_options_and_sessions_to_practices(db_session):
    from app.analytics.dashboards import people, practices

    today = date(2099, 1, 5)
    db_session.add_all([
        _session('kind-practice', today, kind='practice', activity='Run', workout_type='Endurance'),
        _session('kind-event', today, kind='event', category='social', activity='Event', workout_type='Event'),
        _session('kind-future', today + timedelta(days=1), activity='Future', workout_type='Future'),
    ])
    db_session.flush()
    dashboard = practices.DASHBOARD
    with patch('app.utils.today_central', return_value=today):
        options = _option_values(dashboard)
        assert options['activities'] == ['Run']
        assert options['workout_types'] == ['Endurance']
        assert options['kinds'] == ['practice']
        filters = parse_filters(MultiDict({'activity': ['Run', 'Event'], 'workout_type': ['Endurance', 'Event'],
                                           'kind': 'event'}), dashboard)
        assert filters.activities == ['Run'] and filters.workout_types == ['Endurance']
        assert filters.kinds == ['practice']
        assert [s.session_key for s in base.load_sessions(filters)] == ['task13:kind-practice']
        assert _option_values(people.DASHBOARD)['activities'] == ['Event', 'Run']


def test_location_options_disambiguate_spots(db_session):
    locations = [PracticeLocation(name='Test Park', spot=spot) for spot in ('North trail', 'South trail', '')]
    db_session.add_all(locations)
    db_session.flush()
    db_session.add_all([
        _session(f'spot-{i}', date(2099, 1, 5), location_id=location.id, location_name=location.name)
        for i, location in enumerate(locations)
    ])
    db_session.flush()
    with patch('app.utils.today_central', return_value=date(2099, 1, 5)):
        options = dict(base.filter_options(D)['location_ids'])
    assert [options[location.id] for location in locations] == [
        'Test Park - North trail', 'Test Park - South trail', 'Test Park']


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
        options = _option_values(D)
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
    rsvp = PracticeAttendance(session_id=matching.id, slack_uid='UFAKE1301',
                              person_key='slack:UFAKE1301', role='rsvp', source='app')
    lead = PracticeAttendance(session_id=matching.id, slack_uid='UFAKE1302',
                              person_key='slack:UFAKE1302', role='lead', source='app')
    other = PracticeAttendance(session_id=excluded.id, slack_uid='UFAKE1303',
                              person_key='slack:UFAKE1303', role='rsvp', source='app')
    db_session.add_all([rsvp, lead, other])
    db_session.flush()
    f = base.Filters(seasons=['2099 Test'], date_from=date(2099, 1, 5), date_to=date(2099, 1, 5),
                     days=['Monday'], activities=['Strength'], workout_types=['Circuit'], formats=['split'])
    assert base.apply_filters(PracticeSession.query, f).all() == [matching]
    rows = base.load_attendance([matching.id])
    assert [(r.session_id, r.slack_uid, r.slot, r.role) for r in rows] == [(matching.id, 'UFAKE1301', None, 'rsvp')]
    assert tuple(rows[0]._mapping) == ('session_id', 'slack_uid', 'person_key', 'user_id', 'slot', 'role')
    assert rows[0].person_key == 'slack:UFAKE1301' and rows[0].user_id is None
    assert [r.slack_uid for r in base.load_attendance([matching.id], role='lead')] == ['UFAKE1302']
    assert base.load_attendance([]) == []


def test_load_attendance_accepts_multiple_roles_and_people_without_slack(db_session):
    from app.models import User

    user = User(first_name='Fake', last_name='Tester', email='task10@example.invalid')
    session = _session('roles', date(2099, 1, 5))
    db_session.add_all([user, session])
    db_session.flush()
    db_session.add_all([
        PracticeAttendance(session_id=session.id, person_key=f'user:{user.id}', user_id=user.id,
                           role='signup', source='app'),
        PracticeAttendance(session_id=session.id, person_key='slack:UFAKE0001', slack_uid='UFAKE0001',
                           role='rsvp', source='app'),
        PracticeAttendance(session_id=session.id, person_key='slack:UFAKE0002', slack_uid='UFAKE0002',
                           role='decline', source='app'),
    ])
    db_session.flush()
    rows = base.load_attendance([session.id], role=('rsvp', 'signup'))
    assert [(r.person_key, r.user_id, r.slack_uid, r.role) for r in rows] == [
        (f'user:{user.id}', user.id, None, 'signup'), ('slack:UFAKE0001', None, 'UFAKE0001', 'rsvp')]
    assert base.load_attendance([session.id], role=()) == []


def test_footer_uses_latest_sync_not_post_date_and_central_timezone(db_session):
    db_session.query(AppConfig).filter_by(key='analytics_sync_status').delete()
    before = base.footer()['needs_review']
    message = SlackArchiveMessage(channel_id='CFAKE13', ts='1300000000.001',
                                  posted_at=datetime(2090, 1, 1), synced_at=datetime(2099, 1, 6, 2), raw={})
    flagged = _session('review', date(2099, 1, 5), needs_review=True)
    db_session.add_all([message, flagged])
    db_session.flush()
    footer = base.footer()
    assert footer['data_through'] == 'Jan 05, 2099 08:00 PM CST'
    assert footer['needs_review'] == before + 1


@pytest.mark.parametrize('archive_day', [1, 10])
def test_footer_prefers_latest_channel_status_over_archive_sync(db_session, archive_day):
    db_session.query(SlackArchiveMessage).delete()
    db_session.add(SlackArchiveMessage(channel_id='CFAKE13', ts='1300000000.001',
                                       posted_at=datetime(2090, 1, 1),
                                       synced_at=datetime(2099, 1, archive_day), raw={}))
    AppConfig.set('analytics_sync_status', {SYNC_CHANNELS[0]: '2099-01-06T02:00:00',
                                          SYNC_CHANNELS[1]: '2099-01-04T02:00:00'}, category='analytics')
    db_session.flush()
    assert base.footer()['data_through'] == 'Jan 05, 2099 08:00 PM CST'


def test_footer_ignores_newer_status_for_removed_channel(db_session):
    AppConfig.set('analytics_sync_status', {SYNC_CHANNELS[0]: '2099-01-06T02:00:00',
                                          SYNC_CHANNELS[1]: '2099-01-04T02:00:00',
                                          'CFAKEREMOVED': '2099-01-10T02:00:00'}, category='analytics')
    db_session.flush()
    assert base.footer()['data_through'] == 'Jan 05, 2099 08:00 PM CST'


def test_footer_with_empty_sync_status_has_no_success_time(db_session):
    db_session.add(SlackArchiveMessage(channel_id='CFAKE13', ts='1300000000.001',
                                       posted_at=datetime(2090, 1, 1),
                                       synced_at=datetime(2099, 1, 6, 2), raw={}))
    AppConfig.set('analytics_sync_status', {}, category='analytics')
    db_session.flush()
    assert base.footer()['data_through'] is None


@pytest.mark.parametrize('attribute, selected', [
    ('seasons', ['2099 Test']), ('days', ['Monday']), ('activities', ['Strength']),
    ('workout_types', ['Circuit']), ('formats', ['split']), ('kinds', ['practice']),
    ('date_from', date(2099, 1, 5)), ('date_to', date(2099, 1, 5)),
])
def test_each_filter_changes_the_query(db_session, attribute, selected):
    matching = _session('selected', date(2099, 1, 5), activity='Strength', workout_type='Circuit', format='split')
    other_day = date(2099, 1, 4) if attribute == 'date_from' else date(2099, 1, 6)
    excluded = _session('not-selected', other_day, activity='Run', workout_type='Other', format='single', kind='event', category='social')
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
        values = _option_values(D)
        assert base.load_sessions(base.Filters(location_ids=[past_location.id])) == [spring]
        assert future_location.id not in base.get_filter_domains()['location_ids']
    assert (past_location.id, past_location.name) in options['location_ids']
    assert (future_location.id, future_location.name) not in options['location_ids']
    seasons = [s for s in values['seasons'] if s.startswith('2099')]
    assert seasons == ['2099 Fall/Winter', '2099 Spring/Summer']
    assert values['days'].index('Monday') < values['days'].index('Sunday')

