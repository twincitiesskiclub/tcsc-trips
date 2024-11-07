from flask import Blueprint, render_template, abort
from ..models import Trip

trips = Blueprint('trips', __name__)

@trips.route('/training-trip')
def get_training_trip_page():
    trip = Trip.query.filter_by(slug='training-trip').first_or_404()
    return render_template('training-trip.html', trip=trip)

@trips.route('/sisu-ski-fest')
def get_training_trip_2_page():
    trip = Trip.query.filter_by(slug='sisu-ski-fest').first_or_404()
    return render_template('sisu-ski-fest.html', trip=trip)
