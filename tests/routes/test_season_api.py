"""The route is thin: selection and shaping are unit-tested in tests/seasons/.
Most of these tests cover wiring, headers, and the empty-database case, so
they stub the query rather than seeding rows. One test (below) seeds a real
Season through the ORM instead, so a column rename on the model can't leave
this whole file green while the live endpoint 500s."""
import json
import uuid
from datetime import datetime, timedelta

import pytest

import app.routes.season_api as season_api
from app import create_app
from app.models import Season, db


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


@pytest.fixture
def seeded_season_type(app):
    """Seed one real Season row via the ORM, unmonkeypatched, against the real
    local development database (see tests/routes/conftest.py). Yields the
    season_type -- rather than the row's `id`/`primary`-ness -- so the test
    only has to find its own row in `by_type`, not assume it's the soonest
    season in a database that may hold other real rows.

    Cleans up in a finally so a failed assertion above still deletes the row;
    leftover rows silently changing local data is a known problem in this
    repo (see tests/seasons/conftest patterns and CLAUDE.md notes on the
    shared dev DB).
    """
    unique = uuid.uuid4().hex[:8]
    season_type = f'api-test-{unique}'
    now = datetime.utcnow()
    with app.app_context():
        season = Season(
            name=f'API Test Season {unique}',
            season_type=season_type,
            year=now.year,
            start_date=now.date(),
            end_date=(now + timedelta(days=180)).date(),
            price_cents=12345,
            returning_start=datetime(2026, 8, 28, 17, 0, 0),
            returning_end=datetime(2026, 9, 2, 5, 0, 0),
            new_start=datetime(2026, 9, 3, 17, 0, 0),
            new_end=datetime(2026, 9, 20, 5, 0, 0),
        )
        db.session.add(season)
        db.session.commit()
        season_id = season.id
    try:
        yield season_type
    finally:
        with app.app_context():
            row = db.session.get(Season, season_id)
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_serializes_a_real_orm_backed_season(client, seeded_season_type):
    """Every other test in this file monkeypatches `_all_seasons`, and
    tests/seasons/test_payload.py exercises `serialize_season` only against a
    dataclass `StubSeason`. Nothing hits the real `Season` model end to end --
    a renamed or retyped column would leave the whole suite green while
    `/api/season` 500s in production, which the site would then quietly
    absorb as a `fallback` build. This test seeds a real row and hits the
    endpoint for real, with no monkeypatching."""
    resp = client.get('/api/season')
    assert resp.status_code == 200
    body = json.loads(resp.data)

    entry = body['by_type'][seeded_season_type]
    assert entry['season_type'] == seeded_season_type
    assert entry['price_cents'] == 12345
    assert entry['returning_start'] == '2026-08-28T17:00:00Z'
    assert entry['returning_end'] == '2026-09-02T05:00:00Z'
    assert entry['new_start'] == '2026-09-03T17:00:00Z'
    assert entry['new_end'] == '2026-09-20T05:00:00Z'
