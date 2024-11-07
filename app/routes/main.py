from flask import Blueprint, render_template
from ..models import Trip
from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/')
def get_home_page():
    active_trips = Trip.query.filter(
        Trip.status == 'active',
        Trip.signup_end > datetime.utcnow()
    ).order_by(Trip.start_date).all()
    return render_template('index.html', trips=active_trips)
