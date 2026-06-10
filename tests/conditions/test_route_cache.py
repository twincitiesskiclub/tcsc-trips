"""Cache behavior for /api/conditions: serve-stale, background refresh,
and never clobbering a good body with an error body."""
import time

import app.routes.conditions as conditions_route
from app import create_app
from tests.conditions.conftest import _stub_conditions_response


def _counting_build():
    """Builder stub that tags each body with its build number."""
    calls = {'n': 0}

    def build():
        calls['n'] += 1
        body = _stub_conditions_response()
        body['updated_at'] = f'build-{calls["n"]}'
        return body

    return build, calls


def _error_build():
    body = _stub_conditions_response()
    for loc in body['locations']:
        loc['temp_f'] = None
    body['error'] = 'upstream unavailable'
    return body


def _join_rebuild_thread():
    thread = conditions_route._rebuild_thread
    assert thread is not None, 'expected a background rebuild thread'
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_second_request_within_ttl_does_not_rebuild(monkeypatch):
    build, calls = _counting_build()
    monkeypatch.setattr(conditions_route, 'build_conditions_response', build)
    client = create_app().test_client()

    first = client.get('/api/conditions').get_json()
    second = client.get('/api/conditions').get_json()

    assert calls['n'] == 1
    assert first['updated_at'] == second['updated_at'] == 'build-1'


def test_expired_body_served_immediately_then_swapped_in_background(monkeypatch):
    build, calls = _counting_build()
    monkeypatch.setattr(conditions_route, 'build_conditions_response', build)
    client = create_app().test_client()

    assert client.get('/api/conditions').get_json()['updated_at'] == 'build-1'

    # Expire the cache: the next request must still serve the stale body
    # without waiting on the rebuild.
    conditions_route._cache['expires_at'] = 0
    assert client.get('/api/conditions').get_json()['updated_at'] == 'build-1'

    _join_rebuild_thread()
    assert calls['n'] == 2
    assert client.get('/api/conditions').get_json()['updated_at'] == 'build-2'


def test_failed_rebuild_keeps_last_good_body_with_short_retry(monkeypatch):
    build, _calls = _counting_build()
    monkeypatch.setattr(conditions_route, 'build_conditions_response', build)
    client = create_app().test_client()

    assert client.get('/api/conditions').get_json()['updated_at'] == 'build-1'

    # Now the upstream goes down: rebuilds produce an all-None error body.
    monkeypatch.setattr(conditions_route, 'build_conditions_response', _error_build)
    conditions_route._cache['expires_at'] = 0
    assert client.get('/api/conditions').get_json()['updated_at'] == 'build-1'

    _join_rebuild_thread()
    body = client.get('/api/conditions').get_json()
    assert body['updated_at'] == 'build-1'
    assert 'error' not in body

    # Retry window is the short 60s one, not the full 300s TTL.
    remaining = conditions_route._cache['expires_at'] - time.time()
    assert 0 < remaining <= conditions_route._RETRY_TTL_SECONDS + 1


def test_error_body_stored_only_when_no_good_body_exists(monkeypatch):
    monkeypatch.setattr(conditions_route, 'build_conditions_response', _error_build)
    client = create_app().test_client()

    # Cold start straight into an outage: the error body is served and cached
    # with the short retry expiry.
    body = client.get('/api/conditions').get_json()
    assert body['error'] == 'upstream unavailable'
    remaining = conditions_route._cache['expires_at'] - time.time()
    assert 0 < remaining <= conditions_route._RETRY_TTL_SECONDS + 1
