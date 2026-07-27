"""POST /admin/practices/settings/practice-days — `time` validation.

The route validated `day` and `defaults` but never `time`, and a bad time is
silent everywhere downstream: expected_slots() skips an unusable entry with a
single log line, so that whole weekday disappears from drafting for the entire
two-month horizon while the readiness digest still reports every surviving
draft as ready. Nothing pages anyone — the schedule just gets smaller.

The reachable path is not a hand-crafted payload: the config page's
`<input type="time">` submits "" the moment an admin clears the field.

Runs against the real local dev database (see tests/practices/conftest.py), so
the `practice_days` AppConfig row is saved and restored rather than deleted —
these tests must not decide the club's practice schedule.
"""

import pytest

from app.models import AppConfig, db

_ENDPOINT = '/admin/practices/settings/practice-days'


@pytest.fixture(autouse=True)
def preserve_practice_days(db_session):
    """Save/restore the real practice_days row (or its absence).

    A plain delete would silently change the drafting schedule for whoever
    runs the suite next; dev currently has no row at all, and prod may.
    """
    existing = AppConfig.query.filter_by(key='practice_days').first()
    had_row = existing is not None
    original = (
        (existing.value, existing.description, existing.category)
        if had_row else None
    )
    yield
    db.session.rollback()
    if had_row:
        value, description, category = original
        AppConfig.set(key='practice_days', value=value,
                      description=description, category=category)
    else:
        AppConfig.query.filter_by(key='practice_days').delete()
    db.session.commit()


def _post(admin_client, entries):
    return admin_client.post(_ENDPOINT, json={'practice_days': entries})


def test_valid_times_are_accepted(admin_client):
    response = _post(admin_client, [
        {'day': 'tuesday', 'time': '18:15', 'active': True},
        {'day': 'saturday', 'time': '09:00', 'active': True},
        {'day': 'sunday', 'time': '00:00', 'active': False},
        {'day': 'friday', 'time': '23:59', 'active': True},
    ])
    assert response.status_code == 200, response.get_json()
    stored = AppConfig.get('practice_days')
    assert [e['time'] for e in stored] == ['18:15', '09:00', '00:00', '23:59']


def test_a_cleared_time_field_is_rejected(admin_client):
    """The one-keystroke case: clearing the time input submits "".

    Rejecting it at the door is what makes the downstream default safe to
    reason about — the config never holds a value that needs interpreting.
    """
    response = _post(admin_client, [
        {'day': 'tuesday', 'time': '', 'active': True},
    ])
    assert response.status_code == 400
    error = response.get_json()['error']
    assert 'tuesday' in error, 'the error must name the offending day'
    assert 'HH:MM' in error, 'and say what a good value looks like'


@pytest.mark.parametrize('bad_time', [
    '25:00',   # parses as ints, then explodes building the datetime
    '18:60',
    '9:00',    # unpadded — real inputs always pad, so reject the ambiguity
    'six pm',
    '18:15:00',
    None,
    18,
])
def test_unusable_times_are_rejected(admin_client, bad_time):
    response = _post(admin_client, [
        {'day': 'tuesday', 'time': bad_time, 'active': True},
    ])
    assert response.status_code == 400, (
        f'{bad_time!r} must not reach the config: expected_slots would drop '
        f'Tuesday from the whole horizon, or the bootstrap job would die'
    )


def test_a_rejected_payload_leaves_the_stored_config_untouched(admin_client):
    """Validation happens before the write, so one bad entry can't half-apply
    a payload and leave the schedule in a state nobody chose.
    """
    ok = _post(admin_client, [
        {'day': 'tuesday', 'time': '18:15', 'active': True},
    ])
    assert ok.status_code == 200

    rejected = _post(admin_client, [
        {'day': 'thursday', 'time': '19:20', 'active': True},
        {'day': 'saturday', 'time': '25:00', 'active': True},
    ])
    assert rejected.status_code == 400
    assert AppConfig.get('practice_days') == [
        {'day': 'tuesday', 'time': '18:15', 'active': True},
    ], 'the earlier good config must survive a rejected write intact'


def test_a_missing_time_key_is_still_allowed(admin_client):
    """`time` stays optional — expected_slots defaults it to 18:00. Only a
    present-but-unusable value is an error.
    """
    response = _post(admin_client, [{'day': 'tuesday', 'active': True}])
    assert response.status_code == 200
