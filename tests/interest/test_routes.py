from app.interest import service
from app.interest.models import InterestSignup

from .conftest import TEST_DOMAIN

EMAIL = f'pat{TEST_DOMAIN}'


def post(client, **fields):
    data = {'name': 'Pat Prospect', 'email': EMAIL, 'phone': '', service.HONEYPOT: ''}
    data.update(fields)
    return client.post('/interest', data=data)


def count(app):
    with app.app_context():
        return InterestSignup.query.filter_by(email=EMAIL).count()


def test_get_renders_form(client):
    resp = client.get('/interest')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="email"' in html
    assert "Reply STOP to opt out." in html


def test_post_saves_and_thanks(app, client):
    resp = post(client)
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 1


def test_resubmit_shows_same_thanks(app, client):
    post(client)
    resp = post(client, name='Pat Again')
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 1


def test_honeypot_thanks_but_saves_nothing(app, client):
    resp = post(client, **{service.HONEYPOT: 'http://spam.example'})
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 0


def test_bad_phone_rerenders_with_values(app, client):
    resp = post(client, phone='12345')
    assert resp.status_code == 400
    html = resp.get_data(as_text=True)
    assert '10-digit US cell number' in html
    assert 'value="Pat Prospect"' in html
    assert 'value="12345"' in html
    assert count(app) == 0


def test_cross_origin_post_needs_no_csrf_token(app):
    """The marketing site cannot carry the app's CSRF token. Run with CSRF
    enforcement on (TESTING off) and prove an unrelated POST is still
    rejected, so the pass below is the exemption and not a disabled check."""
    app.config.update(TESTING=False, WTF_CSRF_ENABLED=True)
    c = app.test_client()
    resp = c.post('/interest',
                  data={'name': 'Pat Prospect', 'email': EMAIL, 'phone': ''},
                  headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.status_code == 200
    assert count(app) == 1
    # Control: an existing, non-exempt POST route is still rejected. CSRF
    # runs before the view, so nothing is deleted.
    assert c.post('/admin/trips/999999999/delete').status_code == 400


def test_home_page_shows_form_when_registration_closed(client):
    # The scratch DB has no season with an open window today.
    html = client.get('/').get_data(as_text=True)
    assert 'action="/interest"' in html
