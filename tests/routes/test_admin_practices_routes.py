"""Tests for app.routes.admin_practices page renders."""

import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def admin_client(client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['user'] = {'email': 'tester@twincitiesskiclub.org', 'name': 'Tester'}
    return client


def test_new_practice_route_renders_create_mode(admin_client, db_session):
    resp = admin_client.get('/admin/practices/new')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Create mode: title says "New Practice" and there is no context rail yet.
    assert 'New Practice' in body
    assert 'Lead Confirmations' not in body


def test_new_practice_route_requires_auth(client, db_session):
    resp = client.get('/admin/practices/new')
    # Unauthenticated users are redirected to login.
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')
