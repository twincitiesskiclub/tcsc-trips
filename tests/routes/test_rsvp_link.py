"""The SMS link opens the fixed kickoff post without a club-site login."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask

from app.routes.main import main
from app.security import init_security


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.anchors = {}
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.anchors[attrs.get('id')] = attrs.get('href')
        elif tag == 'script':
            self.scripts.append(attrs.get('src'))


@pytest.fixture
def client():
    application = Flask('app')
    application.config['SECRET_KEY'] = 'rsvp-route-test-only'
    application.register_blueprint(main)
    init_security(application, 'production')
    return application.test_client()


@pytest.mark.parametrize('path', [
    '/rsvp', '/rsvp/', '/rsvp?next=https://example.com&ts=1',
])
def test_anonymous_sms_link_keeps_the_exact_post_destination(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.mimetype == 'text/html'
    assert response.headers['Cache-Control'] == 'no-store'
    links = Links(response.get_data(as_text=True))
    native = urlsplit(links.anchors['open-rsvp'])
    assert (native.scheme, native.netloc) == ('slack', 'channel')
    assert parse_qs(native.query) == {
        'team': ['T02J2AVLSCT'],
        'id': ['C0B2VN1LU11'],
        'ts': ['1788546377.776679'],
        'thread_ts': ['1788546377.776679'],
        'host': ['slack.com'],
    }
    assert links.anchors['browser-rsvp'] == (
        'https://twincitiesskiclub.slack.com/archives/'
        'C0B2VN1LU11/p1788546377776679'
    )


def test_auto_launch_script_is_served_under_the_public_csp(client):
    response = client.get('/rsvp')
    assert response.status_code == 200
    links = Links(response.get_data(as_text=True))
    assert links.scripts == ['/static/rsvp.js']
    assert "script-src 'self';" in response.headers['Content-Security-Policy']
    script = client.get(links.scripts[0])
    assert script.status_code == 200
    assert script.mimetype in {'text/javascript', 'application/javascript'}
