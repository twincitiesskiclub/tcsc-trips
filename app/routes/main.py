from flask import Blueprint, render_template
from ..models import Trip
from datetime import datetime
import pytz

main = Blueprint('main', __name__)

@main.route('/')
def get_home_page():
    # Get current time in US Central timezone
    central = pytz.timezone('America/Chicago')
    current_time = datetime.now(central)
    
    active_trips = Trip.query.filter(
        Trip.status == 'active',
        Trip.signup_end > current_time
    ).order_by(Trip.start_date).all()
    return render_template('index.html', trips=active_trips)
