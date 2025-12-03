import os
from dotenv import load_dotenv, find_dotenv
import stripe

def load_stripe_config():
    """Load Stripe configuration from environment variables"""
    load_dotenv(find_dotenv())
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    stripe.api_version = os.getenv('STRIPE_API_VERSION')
    if not stripe.api_key:
        raise ValueError("Missing STRIPE_SECRET_KEY in environment variables")

def configure_database(app, environment):
    """Configure the database based on environment.

    Uses DATABASE_URL if present (PostgreSQL), otherwise falls back to SQLite.
    """
    # Check for DATABASE_URL first (PostgreSQL on Render)
    database_url = os.getenv('DATABASE_URL')

    if database_url:
        # Render provides postgres:// but SQLAlchemy requires postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        # PostgreSQL connection pooling settings
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'pool_recycle': 300,
            'pool_pre_ping': True,
        }
    else:
        # Fall back to SQLite for local development
        base_dir = os.path.abspath(os.path.dirname(__file__))

        db_paths = {
            'production': '/var/lib/app.db',
            'development': '/var/lib/app_dev.db',
            'testing': os.path.join(base_dir, 'instance', 'test.db')
        }

        if environment not in db_paths:
            raise ValueError(f"Invalid FLASK_ENV value: {environment}")

        if environment == 'testing':
            os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)

        db_path = db_paths[environment]
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
