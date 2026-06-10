from unittest.mock import patch
from app.conditions.service import build_conditions_response


def test_build_conditions_returns_one_entry_per_location():
    with patch('app.conditions.service.get_current_temp_f', return_value=20), \
         patch('app.conditions.service.get_wind_chill_f', return_value=12), \
         patch('app.conditions.service.get_trail_conditions', return_value='firm'):
        resp = build_conditions_response()
    assert 'updated_at' in resp
    assert len(resp['locations']) == 4
    first = resp['locations'][0]
    assert first['id'] == 'wirth'
    assert first['temp_f'] == 20
    assert first['wax_band'] == 'blue'
    assert first['wax_label'] == 'Blue wax · firm snow'


def test_build_conditions_handles_missing_data_gracefully():
    with patch('app.conditions.service.get_current_temp_f', return_value=None), \
         patch('app.conditions.service.get_wind_chill_f', return_value=None), \
         patch('app.conditions.service.get_trail_conditions', return_value=None):
        resp = build_conditions_response()
    assert resp['locations'][0]['temp_f'] is None
    assert resp['locations'][0]['wax_band'] is None
    assert resp.get('error') == 'upstream unavailable' or all(
        loc['temp_f'] is None for loc in resp['locations']
    )
