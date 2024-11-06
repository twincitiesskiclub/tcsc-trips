import os
from dotenv import load_dotenv, find_dotenv
import stripe
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def load_stripe_config():
    """Load Stripe configuration from environment variables"""
    load_dotenv(find_dotenv())
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    stripe.api_version = os.getenv('STRIPE_API_VERSION')
    if not stripe.api_key:
        raise ValueError("Missing STRIPE_SECRET_KEY in environment variables")

def configure_database(app, environment):
    """Configure the database based on the environment"""
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
