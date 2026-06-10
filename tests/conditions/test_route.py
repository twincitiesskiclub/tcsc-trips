import json
from app import create_app


def _client(debug=False):
    app = create_app()
    app.debug = debug
    return app.test_client()


def test_get_conditions_returns_json():
    client = _client()
    resp = client.get('/api/conditions')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('application/json')
    body = json.loads(resp.data)
    assert 'updated_at' in body
    assert isinstance(body['locations'], list)
    assert len(body['locations']) == 4


def test_get_conditions_always_varies_on_origin():
    client = _client()
    resp = client.get('/api/conditions')
    assert resp.headers.get('Vary') == 'Origin'
    resp = client.get('/api/conditions', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Vary') == 'Origin'


def test_get_conditions_sets_cors_for_marketing_site():
    client = _client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://twincitiesskiclub.org'


def test_get_conditions_sets_cors_for_www_subdomain():
    client = _client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://www.twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://www.twincitiesskiclub.org'


def test_get_conditions_sets_cors_for_staging_origin():
    client = _client()
    resp = client.get('/api/conditions',
                      headers={'Origin': 'https://tcsc-marketing.onrender.com'})
    assert (resp.headers.get('Access-Control-Allow-Origin')
            == 'https://tcsc-marketing.onrender.com')


def test_get_conditions_rejects_other_origins():
    client = _client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Access-Control-Allow-Origin') is None


def test_get_conditions_allows_localhost_in_debug_only():
    origin = 'http://localhost:4321'
    resp = _client(debug=True).get('/api/conditions', headers={'Origin': origin})
    assert resp.headers.get('Access-Control-Allow-Origin') == origin
    resp = _client(debug=False).get('/api/conditions', headers={'Origin': origin})
    assert resp.headers.get('Access-Control-Allow-Origin') is None
