from datetime import date
from unittest.mock import patch

from app.conditions.birkie import build_birkie_status
from app.conditions.service import build_conditions_response


def test_offseason_is_early_and_names_next_race_year():
    s = build_birkie_status(date(2026, 6, 10), None)
    assert s['status'] == 'early'
    assert s['word'] == '98.6°'
    assert 'Birkie 2027' in s['detail']


def test_january_good_report_is_likely():
    s = build_birkie_status(date(2026, 1, 15), 'good')
    assert s['status'] == 'likely'
    assert 'good' in s['detail']


def test_january_fair_report_is_watch():
    s = build_birkie_status(date(2026, 1, 15), 'fair')
    assert s['status'] == 'watch'


def test_january_no_report_is_watch():
    s = build_birkie_status(date(2026, 1, 15), None)
    assert s['status'] == 'watch'
    assert s['word'] == '100.4°'


def test_november_no_report_is_waiting():
    s = build_birkie_status(date(2025, 11, 5), None)
    assert s['status'] == 'waiting'


def test_february_uses_current_year_as_race_year():
    s = build_birkie_status(date(2027, 3, 1), None)
    assert 'Birkie 2028' in s['detail']


def test_response_includes_birkie_block():
    from types import SimpleNamespace

    wx = SimpleNamespace(temperature_f=20, feels_like_f=12)
    report = SimpleNamespace(
        ski_quality='good',
        report_url=None,
        report_date=None,
        groomed=False,
        groomed_for=None,
    )
    with patch('app.conditions.service.get_weather', return_value=wx), \
         patch('app.conditions.service.get_trail_report', return_value=report):
        resp = build_conditions_response()
    assert set(resp['birkie'].keys()) == {'status', 'word', 'detail'}
    ids = [loc['id'] for loc in resp['locations']]
    assert ids == ['wirth', 'elm', 'hyland', 'telemark']
