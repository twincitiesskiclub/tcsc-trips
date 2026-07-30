from app import create_app
from app.routes.marketing_cors import ALLOWED_ORIGINS, origin_allowed


def _ctx(debug=False):
    app = create_app()
    app.debug = debug
    return app


def test_the_marketing_origins_are_allowed():
    app = _ctx()
    with app.app_context():
        assert origin_allowed('https://twincitiesskiclub.org')
        assert origin_allowed('https://www.twincitiesskiclub.org')
        assert origin_allowed('https://tcsc-marketing.onrender.com')


def test_unknown_and_empty_origins_are_rejected():
    app = _ctx()
    with app.app_context():
        assert not origin_allowed('https://evil.com')
        assert not origin_allowed('')


def test_localhost_is_allowed_only_in_debug():
    app = _ctx(debug=True)
    with app.app_context():
        assert origin_allowed('http://localhost:4321')

    app = _ctx(debug=False)
    with app.app_context():
        assert not origin_allowed('http://localhost:4321')


def test_the_allowlist_still_covers_the_conditions_origins():
    # conditions and the season API must not drift apart.
    assert 'https://twincitiesskiclub.org' in ALLOWED_ORIGINS
    assert 'https://www.twincitiesskiclub.org' in ALLOWED_ORIGINS
