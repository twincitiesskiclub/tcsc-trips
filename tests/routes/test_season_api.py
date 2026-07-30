"""The route is thin: selection and shaping are unit-tested in tests/seasons/.
These tests cover wiring, headers, and the empty-database case, so they stub
the query rather than seeding rows."""
import json

import app.routes.season_api as season_api
from app import create_app


def _client(monkeypatch, seasons, debug=False):
    monkeypatch.setattr(season_api, '_all_seasons', lambda: seasons)
    app = create_app()
    app.debug = debug
    return app.test_client()


class StubSeason:
    id = 1
    name = '2026 Fall/Winter'
    season_type = 'fall/winter'
    year = 2026
    price_cents = 20500
    returning_start = __import__('datetime').datetime(2026, 8, 28, 17, 0, 0)
    returning_end = __import__('datetime').datetime(2026, 9, 2, 5, 0, 0)
    new_start = __import__('datetime').datetime(2026, 9, 3, 17, 0, 0)
    new_end = __import__('datetime').datetime(2026, 9, 20, 5, 0, 0)


def test_returns_json_with_the_expected_shape(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('application/json')
    body = json.loads(resp.data)
    assert set(body) == {'generated_at', 'primary', 'by_type'}
    assert body['primary']['season_type'] == 'fall/winter'
    assert body['by_type']['fall/winter']['returning_start'] == '2026-08-28T17:00:00Z'


def test_returns_a_null_primary_rather_than_erroring_on_an_empty_database(monkeypatch):
    client = _client(monkeypatch, [])
    resp = client.get('/api/season')
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['primary'] is None
    assert body['by_type'] == {}


def test_exposes_no_computed_state(monkeypatch):
    # The browser derives state from the timestamps; a server-computed state
    # would be stale the moment a window boundary passed.
    client = _client(monkeypatch, [StubSeason()])
    body = json.loads(client.get('/api/season').data)
    assert 'state' not in body
    assert 'state' not in body['primary']


def test_always_varies_on_origin(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    assert client.get('/api/season').headers.get('Vary') == 'Origin'
    resp = client.get('/api/season', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Vary') == 'Origin'
    assert 'Access-Control-Allow-Origin' not in resp.headers


def test_sets_cors_for_the_marketing_site(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season', headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://twincitiesskiclub.org'


def test_is_publicly_cacheable(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season')
    assert resp.headers.get('Cache-Control') == 'public, max-age=300'
