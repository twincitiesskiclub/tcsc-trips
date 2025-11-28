from flask import Blueprint, render_template
from ..models import Trip

trips = Blueprint('trips', __name__)


@trips.route('/<slug>')
def get_trip_page(slug):
    """Generic trip detail page handler for any trip slug."""
    trip = Trip.query.filter_by(slug=slug).first_or_404()
    return render_template(f'trips/{slug}.html', trip=trip)
