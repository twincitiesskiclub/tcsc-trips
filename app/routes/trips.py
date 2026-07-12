from flask import Blueprint, render_template
from datetime import datetime

from ..models import Trip
from ..utils import format_datetime_central

trips = Blueprint('trips', __name__)


@trips.route('/<slug>')
def get_trip_page(slug):
    """Generic trip detail page handler for any trip slug."""
    trip = Trip.query.filter_by(slug=slug).first_or_404()
    now = datetime.utcnow()
    registration_open = (
        trip.status == 'active'
        and trip.signup_start <= now <= trip.signup_end
    )
    if trip.status != 'active':
        registration_message = 'Trip registration is not currently open.'
    elif now < trip.signup_start:
        opens_at = format_datetime_central(trip.signup_start)
        registration_message = f'Trip registration opens {opens_at}.'
    else:
        registration_message = 'Trip registration has closed.'

    return render_template(
        f'trips/{slug}.html',
        trip=trip,
        registration_open=registration_open,
        registration_message=registration_message,
    )
