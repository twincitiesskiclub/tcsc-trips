from flask import Blueprint, render_template, abort
from ..models import Trip

trips = Blueprint('trips', __name__)

@trips.route('/training-trip')
def get_training_trip_page():
    trip = Trip.query.filter_by(slug='training-trip').first_or_404()
    return render_template('trips/training-trip.html', trip=trip)

@trips.route('/sisu-ski-fest')
def get_sisu_ski_fest_page():
    trip = Trip.query.filter_by(slug='sisu-ski-fest').first_or_404()
    return render_template('trips/sisu-ski-fest.html', trip=trip)

@trips.route('/pre-birkie')
def get_pre_birkie_page():
    trip = Trip.query.filter_by(slug='pre-birkie').first_or_404()
    return render_template('trips/pre-birkie.html', trip=trip)

@trips.route('/birkie')
def get_birkie_page():
    trip = Trip.query.filter_by(slug='birkie').first_or_404()
    return render_template('trips/birkie.html', trip=trip)

@trips.route('/cuyuna')
def get_cuyuna_page():
    trip = Trip.query.filter_by(slug='cuyuna').first_or_404()
    return render_template('trips/cuyuna.html', trip=trip)

@trips.route('/great-bear-chase')
def get_great_bear_chase_page():
    trip = Trip.query.filter_by(slug='great-bear-chase').first_or_404()
    return render_template('trips/great-bear-chase.html', trip=trip)
