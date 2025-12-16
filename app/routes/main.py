from flask import Blueprint, render_template
from ..models import Trip, Season, SocialEvent
from ..utils import get_current_times

main = Blueprint('main', __name__)


@main.route('/')
def get_home_page():
    # Get current times for display (Central) and database comparisons (UTC)
    times = get_current_times()
    now_utc = times['utc']

    active_trips = Trip.query.filter(
        Trip.status == 'active',
        Trip.signup_end > now_utc # Use UTC for DB query
    ).order_by(Trip.start_date).all()

    # Fetch active social events with open signup
    active_social_events = SocialEvent.query.filter(
        SocialEvent.status == 'active',
        SocialEvent.signup_end > now_utc
    ).order_by(SocialEvent.event_date).all()

    # Fetch the most recent season by registration window or start date
    season = (
        Season.query
        .filter(
            (Season.returning_start != None) | (Season.new_start != None)
        )
        .order_by(Season.start_date.desc())
        .first()
    )

    is_season_registration_open = season.is_any_registration_open(now_utc) if season else False

    return render_template('index.html',
                           trips=active_trips,
                           social_events=active_social_events,
                           season=season,
                           now=now_utc, # Pass UTC time for template date comparisons
                           is_season_registration_open=is_season_registration_open)

@main.route('/tri')
def dryland_triathlon_page():
    return render_template('dryland-triathlon.html')

