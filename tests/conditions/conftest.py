"""Keep route tests off the live NWS/SkinnySkI integrations.

The /api/conditions route caches build_conditions_response() at module level,
so each test stubs the builder and resets the cache for isolation.
"""
import pytest

import app.routes.conditions as conditions_route
from app.conditions.locations import LOCATIONS


def _stub_conditions_response() -> dict:
    return {
        'updated_at': '2026-01-15T07:00:00-06:00',
        'locations': [
            {
                'id': loc.id,
                'name': loc.name,
                'temp_f': 20,
                'wind_chill_f': 12,
                'snow_conditions': 'good',
                'wax_band': 'blue',
                'wax_label': 'Blue wax · firm snow',
            }
            for loc in LOCATIONS
        ],
    }


@pytest.fixture(autouse=True)
def _stub_route_conditions(monkeypatch):
    monkeypatch.setattr(
        conditions_route, 'build_conditions_response', _stub_conditions_response
    )
    monkeypatch.setattr(
        conditions_route, '_cache', {'expires_at': 0, 'body': None}
    )
    yield
