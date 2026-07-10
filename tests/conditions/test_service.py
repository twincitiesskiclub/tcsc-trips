from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.conditions import service
from app.conditions.service import build_conditions_response


def _wx(temp_f, feels_like_f):
    return SimpleNamespace(temperature_f=temp_f, feels_like_f=feels_like_f)


def _report(ski_quality='firm', report_url=None, report_date=None,
            groomed=False, groomed_for=None):
    return SimpleNamespace(
        ski_quality=ski_quality,
        report_url=report_url,
        report_date=report_date,
        groomed=groomed,
        groomed_for=groomed_for,
    )


def test_build_conditions_returns_one_entry_per_location():
    with patch('app.conditions.service.get_weather', return_value=_wx(20, 12)), \
         patch('app.conditions.service.get_trail_report',
               return_value=_report(ski_quality='firm')):
        resp = build_conditions_response()
    assert 'updated_at' in resp
    assert len(resp['locations']) == 4
    first = resp['locations'][0]
    assert first['id'] == 'wirth'
    assert first['temp_f'] == 20
    assert first['wind_chill_f'] == 12
    assert first['snow_conditions'] == 'firm'
    assert first['wax_band'] == 'blue'
    assert first['wax_label'] == 'Blue wax · firm snow'


def test_build_conditions_handles_missing_data_gracefully():
    with patch('app.conditions.service.get_weather', return_value=None), \
         patch('app.conditions.service.get_trail_report', return_value=None):
        resp = build_conditions_response()
    first = resp['locations'][0]
    assert first['temp_f'] is None
    assert first['wind_chill_f'] is None
    assert first['snow_conditions'] is None
    assert first['wax_band'] is None
    assert first['wax_label'] is None


def test_build_conditions_includes_trail_provenance_fields():
    report = _report(
        ski_quality='good',
        report_url='https://www.skinnyski.com/trails/report.asp?id=123',
        report_date=datetime(2026, 2, 8),
        groomed=True,
        groomed_for='skate',
    )
    with patch('app.conditions.service.get_weather', return_value=_wx(20, 12)), \
         patch('app.conditions.service.get_trail_report', return_value=report):
        resp = build_conditions_response()
    first = resp['locations'][0]
    assert first['source_url'] == 'https://www.skinnyski.com/trails/report.asp?id=123'
    assert first['report_date'] == '2026-02-08'
    assert first['groomed_for'] == 'skate'


def test_build_conditions_provenance_defaults_to_both_when_groomed_without_discipline():
    report = _report(groomed=True, groomed_for=None)
    with patch('app.conditions.service.get_weather', return_value=_wx(20, 12)), \
         patch('app.conditions.service.get_trail_report', return_value=report):
        resp = build_conditions_response()
    assert resp['locations'][0]['groomed_for'] == 'both'


def test_build_conditions_provenance_null_without_report():
    with patch('app.conditions.service.get_weather', return_value=_wx(20, 12)), \
         patch('app.conditions.service.get_trail_report', return_value=None):
        resp = build_conditions_response()
    first = resp['locations'][0]
    assert first['source_url'] is None
    assert first['report_date'] is None
    assert first['groomed_for'] is None


def test_error_key_present_when_all_temps_missing():
    with patch('app.conditions.service.get_weather', return_value=None), \
         patch('app.conditions.service.get_trail_report', return_value=None):
        resp = build_conditions_response()
    assert resp['error'] == 'upstream unavailable'


def test_error_key_absent_when_some_temps_present():
    with patch('app.conditions.service.get_weather',
               side_effect=[_wx(20, 12), None, None, None]), \
         patch('app.conditions.service.get_trail_report', return_value=None):
        resp = build_conditions_response()
    assert 'error' not in resp


# Adapter wrappers around the real integration modules


def test_get_weather_returns_integration_result():
    wx = _wx(15.0, 5.0)
    with patch.object(service._weather_integration, 'get_weather_forecast',
                      return_value=wx) as mock_forecast:
        result = service.get_weather(44.9956, -93.3252)
    assert result is wx
    args = mock_forecast.call_args[0]
    assert args[0] == 44.9956
    assert args[1] == -93.3252


def test_get_weather_returns_none_on_integration_error():
    with patch.object(service._weather_integration, 'get_weather_forecast',
                      side_effect=RuntimeError('NWS down')):
        assert service.get_weather(44.9956, -93.3252) is None


def test_get_trail_report_passes_canonical_name_and_returns_report():
    condition = _report(ski_quality='good')
    with patch.object(service._trail_integration, 'get_trail_conditions',
                      return_value=condition) as mock_lookup:
        result = service.get_trail_report('Hyland Lake Park Reserve')
    assert result is condition
    mock_lookup.assert_called_once_with('Hyland Lake Park Reserve')


def test_get_trail_report_returns_none_when_no_report():
    with patch.object(service._trail_integration, 'get_trail_conditions',
                      return_value=None):
        assert service.get_trail_report('Theodore Wirth Park') is None


def test_get_trail_report_returns_none_on_integration_error():
    with patch.object(service._trail_integration, 'get_trail_conditions',
                      side_effect=RuntimeError('scrape failed')):
        assert service.get_trail_report('Theodore Wirth Park') is None
