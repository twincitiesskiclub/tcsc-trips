from flask import Blueprint, redirect, url_for

socials = Blueprint('socials', __name__)


@socials.route('/social/<slug>')
def redirect_social(slug):
    """Preserve legacy social links after moving them to Events."""
    return redirect(
        url_for("events.get_event_page", slug=slug),
        code=302,
    )
