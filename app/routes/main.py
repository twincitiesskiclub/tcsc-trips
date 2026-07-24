from flask import Blueprint, redirect, render_template, url_for
from ..events.models import Audience, Event, EventStatus
from ..models import Trip, Season
from ..utils import get_current_times

main = Blueprint('main', __name__)

MARKETING_TRIPS_URL = 'https://twincitiesskiclub.org/trips'


@main.route('/register', strict_slashes=False)
def legacy_register():
    """Retire the Wix-era generic registration path to the app home page."""
    return redirect(url_for('main.get_home_page'), code=301)


@main.route('/trips', strict_slashes=False)
@main.route('/trips/sisu-ski-fest', strict_slashes=False)
def legacy_trip_signup():
    """Send retired trip-signup destinations to the marketing trip ledger."""
    return redirect(MARKETING_TRIPS_URL, code=301)


@main.route('/')
def get_home_page():
    # Get current times for display (Central) and database comparisons (UTC)
    times = get_current_times()
    now_utc = times['utc']

    active_trips = Trip.query.filter(
        Trip.status == 'active',
        Trip.signup_end > now_utc # Use UTC for DB query
    ).order_by(Trip.start_date).all()

    active_events = Event.query.filter(
        Event.status == EventStatus.ACTIVE,
        Event.audience.in_((Audience.EXTERNAL, Audience.BOTH)),
        Event.signup_end > now_utc,
    ).order_by(Event.event_date).all()

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
                           events=active_events,
                           season=season,
                           now=now_utc, # Pass UTC time for template date comparisons
                           is_season_registration_open=is_season_registration_open)

@main.route('/tri')
@main.route('/dryland-triathlon')
def dryland_triathlon_page():
    return redirect('/events/dry-tri-2026', code=302)
