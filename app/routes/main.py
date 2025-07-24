from flask import Blueprint, render_template
from ..models import Trip, Season
from datetime import datetime
import pytz

main = Blueprint('main', __name__)

@main.route('/')
def get_home_page():
    # Get current time in US Central timezone for display consistency
    central = pytz.timezone('America/Chicago')
    now_central = datetime.now(central)
    # Use UTC for database comparisons
    now_utc = datetime.utcnow()

    active_trips = Trip.query.filter(
        Trip.status == 'active',
        Trip.signup_end > now_utc # Use UTC for DB query
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
    
    is_season_registration_open = False
    if season:
        # Check if registration is currently open for returning or new members
        returning_open = season.returning_start and season.returning_end and season.returning_start <= now_utc <= season.returning_end
        new_open = season.new_start and season.new_end and season.new_start <= now_utc <= season.new_end
        is_season_registration_open = returning_open or new_open

    return render_template('index.html', 
                           trips=active_trips, 
                           season=season, 
                           now=now_utc, # Pass UTC time for template date comparisons
                           is_season_registration_open=is_season_registration_open)

@main.route('/tri')
def dryland_triathlon_page():
    return render_template('dryland-triathlon.html')
