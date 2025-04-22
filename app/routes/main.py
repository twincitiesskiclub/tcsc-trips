from flask import Blueprint, render_template
from ..models import Trip, Season
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
    # Fetch the current or next season by registration window or start date
    season = (
        Season.query
        .filter(
            (Season.returning_start != None) | (Season.new_start != None)
        )
        .order_by(Season.start_date.asc())
        .first()
    )
    now = datetime.utcnow()
    return render_template('index.html', trips=active_trips, season=season, now=now)
