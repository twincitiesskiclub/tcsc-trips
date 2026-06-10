import json
from app import create_app


def test_get_conditions_returns_json():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('application/json')
    body = json.loads(resp.data)
    assert 'updated_at' in body
    assert isinstance(body['locations'], list)
    assert len(body['locations']) == 4


def test_get_conditions_sets_cors_for_marketing_site():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://twincitiesskiclub.org'


def test_get_conditions_rejects_other_origins():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Access-Control-Allow-Origin') != 'https://evil.com'
