from flask import Blueprint, render_template

trips = Blueprint('trips', __name__)

@trips.route('/training-trip')
def get_training_trip_page():
    return render_template('training-trip.html')

@trips.route('/training-trip-2')
def get_training_trip_2_page():
    return render_template('training-trip-2.html')
