import os

from flask import Flask
from flask_migrate import Migrate

from .auth import init_oauth
from .config import configure_database, load_stripe_config
from .models import db, SocialEvent
from .routes.admin import admin
from .routes.auth import auth
from .routes.main import main
from .routes.payments import payments
from .routes.registration import registration
from .routes.socials import socials
from .routes.trips import trips


def create_app(environment=None):
    if environment is None:
        environment = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.secret_key = os.getenv('FLASK_SECRET_KEY')

    load_stripe_config()
    configure_database(app, environment)
    init_oauth(app)

    db.init_app(app)
    migrate = Migrate(app, db)

    app.register_blueprint(main)
    app.register_blueprint(trips)
    app.register_blueprint(socials)
    app.register_blueprint(payments)
    app.register_blueprint(admin)
    app.register_blueprint(auth)
    app.register_blueprint(registration)

    # Register template filters
    register_template_filters(app)

    with app.app_context():
        db.create_all()

    return app


def register_template_filters(app):
    """Register custom Jinja2 template filters."""

    @app.template_filter('format_price')
    def format_price(cents):
        """Format price from cents to dollar string (e.g., 5000 -> '$50.00')."""
        if cents is None:
            return '$0.00'
        return f"${cents / 100:.2f}"

    @app.template_filter('format_cents')
    def format_cents(cents):
        """Format price from cents to decimal string without $ (e.g., 5000 -> '50.00').
        Useful for data attributes and form values."""
        if cents is None:
            return '0.00'
        return f"{cents / 100:.2f}"

    @app.template_filter('format_date')
    def format_date(dt, fmt='%b %d, %Y'):
        """Format datetime with optional format string.

        Common formats:
        - '%b %d, %Y' (default): Jan 15, 2025
        - '%Y-%m-%d': 2025-01-15 (ISO date for form inputs)
        - '%Y-%m-%dT%H:%M': 2025-01-15T14:30 (datetime-local input)
        - '%b %d, %Y %I:%M %p': Jan 15, 2025 02:30 PM
        - '%b %d, %Y %I:%M %p %Z': Jan 15, 2025 02:30 PM UTC
        """
        if dt is None:
            return ''
        return dt.strftime(fmt)
