from flask import Blueprint, render_template
from ..models import SocialEvent

socials = Blueprint('socials', __name__)


@socials.route('/social/<slug>')
def get_social_event_page(slug):
    """Social event detail and registration page."""
    social_event = SocialEvent.query.filter_by(slug=slug).first_or_404()
    return render_template('socials/registration.html', event=social_event)
