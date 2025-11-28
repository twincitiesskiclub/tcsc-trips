from flask import Blueprint, redirect, url_for, session, current_app, request
from ..auth import oauth, admin_required, is_allowed_domain
from ..constants import ALLOWED_EMAIL_DOMAIN
from ..errors import flash_error, flash_success

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    session['next_url'] = request.args.get('next') or url_for('admin.get_admin_page')
    redirect_uri = url_for('auth.authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth.route('/authorize')
def authorize():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if user_info:
            session['user'] = {
                'email': user_info['email'],
                'name': user_info['name']
            }
            if not is_allowed_domain(user_info['email']):
                flash_error(f'Unauthorized domain. Access restricted to {ALLOWED_EMAIL_DOMAIN}')
                return redirect(url_for('main.get_home_page'))

            flash_success('Successfully logged in!')
            next_url = session.pop('next_url', url_for('admin.get_admin_page'))
            return redirect(next_url)
    except Exception as e:
        flash_error(f'Authentication failed: {str(e)}')

    return redirect(url_for('main.get_home_page'))

@auth.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('next_url', None)
    flash_success('Successfully logged out')
    return redirect(url_for('main.get_home_page'))