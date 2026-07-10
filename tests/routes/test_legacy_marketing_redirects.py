"""End-to-end destinations for stale marketing-site redirect rules."""

import pytest
from flask import Flask

from app.routes.main import MARKETING_TRIPS_URL, main
from app.routes.trips import trips


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(main)
    app.register_blueprint(trips)
    return app.test_client()


@pytest.mark.parametrize(
    ('path', 'destination'),
    [
        ('/register', '/'),
        ('/register/', '/'),
        ('/trips', MARKETING_TRIPS_URL),
        ('/trips/', MARKETING_TRIPS_URL),
        ('/trips/sisu-ski-fest', MARKETING_TRIPS_URL),
        ('/trips/sisu-ski-fest/', MARKETING_TRIPS_URL),
    ],
)
def test_retired_destination_redirects_permanently(client, path, destination):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 301
    assert response.headers['Location'] == destination
