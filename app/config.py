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

    Requires DATABASE_URL environment variable (PostgreSQL).
    """
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Run ./scripts/dev.sh to start local PostgreSQL via Docker."
        )

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
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
