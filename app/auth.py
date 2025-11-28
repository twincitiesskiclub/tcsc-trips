from functools import wraps
from flask import redirect, url_for, session, flash, current_app, request
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
import os
from urllib.parse import urlencode

from .constants import ALLOWED_EMAIL_DOMAIN

oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth with Google configuration"""
    oauth.init_app(app)

    # Configure Google OAuth
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        client_kwargs={
            'scope': 'openid email profile',
            'prompt': 'select_account'  # Forces account selection each time
        }
    )


def is_allowed_domain(email):
    """Check if email domain is allowed"""
    return email and email.endswith(ALLOWED_EMAIL_DOMAIN)


def admin_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login', next=request.url))

        if not is_allowed_domain(session['user'].get('email')):
            flash(f'Access restricted to {ALLOWED_EMAIL_DOMAIN} domain', 'error')
            return redirect(url_for('main.get_home_page'))

        return f(*args, **kwargs)
    return decorated_function

def handle_oauth_error(error):
    """Handle OAuth errors and return appropriate response"""
    error_msg = str(error)
    if isinstance(error, OAuthError):
        error_msg = "Authentication failed. Please try again."
    flash(error_msg, 'error')
    return redirect(url_for('main.get_home_page'))