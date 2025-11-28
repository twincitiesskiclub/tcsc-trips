from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, Response
from ..auth import admin_required
from ..models import db, Payment, Trip, Season, User, UserSeason
from ..constants import DATE_FORMAT, DATETIME_FORMAT, MIN_PRICE_CENTS, CENTS_PER_DOLLAR
from datetime import datetime, timedelta
import csv
from io import StringIO

admin = Blueprint('admin', __name__)


def validate_season_form(form):
    """Validate and parse season form data.

    Returns:
        tuple: (is_valid, error_message, parsed_data)
        - If valid: (True, None, dict of parsed data)
        - If invalid: (False, error_message, None)
    """
    try:
        # Parse basic fields
        year = int(form['year'])
        season_type = form['season_type']
        name = f"{year} {season_type.title()}"

        # Parse price
        price_cents = None
        if form.get('price_cents'):
            price_cents = int(float(form['price_cents']) * CENTS_PER_DOLLAR)
        if price_cents is None or price_cents < MIN_PRICE_CENTS:
            return (False, 'Price must be at least $1.00 (100 cents).', None)

        # Parse dates
        start_date = datetime.strptime(form['start_date'], DATE_FORMAT)
        end_date = datetime.strptime(form['end_date'], DATE_FORMAT)

        # Validate dates aren't too far in past
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        if start_date < week_ago or end_date < week_ago:
            return (False, 'Season start and end dates cannot be more than a week in the past.', None)

        # Parse registration windows
        returning_start = datetime.strptime(form['returning_start'], DATETIME_FORMAT) if form.get('returning_start') else None
        returning_end = datetime.strptime(form['returning_end'], DATETIME_FORMAT) if form.get('returning_end') else None
        new_start = datetime.strptime(form['new_start'], DATETIME_FORMAT) if form.get('new_start') else None
        new_end = datetime.strptime(form['new_end'], DATETIME_FORMAT) if form.get('new_end') else None

        # Validate registration start dates are before season start
        if returning_start and returning_start >= start_date:
            return (False, 'Returning registration start must be before the season start date.', None)
        if new_start and new_start >= start_date:
            return (False, 'New registration start must be before the season start date.', None)

        # Validate start dates are before end dates
        if start_date >= end_date:
            return (False, 'Season start date must be before end date.', None)
        if returning_start and returning_end and returning_start >= returning_end:
            return (False, 'Returning registration start must be before end.', None)
        if new_start and new_end and new_start >= new_end:
            return (False, 'New registration start must be before end.', None)

        # Parse optional fields
        registration_limit = int(form['registration_limit']) if form.get('registration_limit') else None
        description = form.get('description')

        # Return parsed data
        return (True, None, {
            'name': name,
            'season_type': season_type,
            'year': year,
            'start_date': start_date,
            'end_date': end_date,
            'price_cents': price_cents,
            'returning_start': returning_start,
            'returning_end': returning_end,
            'new_start': new_start,
            'new_end': new_end,
            'registration_limit': registration_limit,
            'description': description,
        })
    except ValueError as e:
        return (False, f'Invalid form data: {str(e)}', None)


def get_season_form_data(form):
    """Prepare form data for re-rendering on validation error."""
    form_data = dict(form)
    form_data['price_cents'] = form.get('price_cents')
    return form_data


def parse_trip_form(form):
    """Parse and validate trip form data.

    Returns:
        dict: Parsed trip data ready for model creation/update
    """
    return {
        'slug': form['slug'],
        'name': form['name'],
        'destination': form['destination'],
        'max_participants_standard': int(form['max_participants_standard']),
        'max_participants_extra': int(form['max_participants_extra']),
        'start_date': datetime.strptime(form['start_date'], DATE_FORMAT),
        'end_date': datetime.strptime(form['end_date'], DATE_FORMAT),
        'signup_start': datetime.strptime(form['signup_start'], DATETIME_FORMAT),
        'signup_end': datetime.strptime(form['signup_end'], DATETIME_FORMAT),
        'price_low': int(float(form['price_low']) * CENTS_PER_DOLLAR),
        'price_high': int(float(form['price_high']) * CENTS_PER_DOLLAR),
        'description': form['description'],
        'status': form['status'],
    }


@admin.route('/admin')
@admin_required
def get_admin_page():
    return render_template('admin/index.html')

@admin.route('/admin/payments')
@admin_required
def get_admin_payments():
    payments = Payment.query.all()
    return render_template('admin/payments.html', payments=payments)

@admin.route('/admin/trips')
@admin_required
def get_admin_trips():
    trips = Trip.query.order_by(Trip.start_date).all()
    return render_template('admin/trips.html', trips=trips)

@admin.route('/admin/trips/new', methods=['GET', 'POST'])
@admin_required
def new_trip():
    if request.method == 'POST':
        try:
            trip = Trip(**parse_trip_form(request.form))
            db.session.add(trip)
            db.session.commit()
            flash('Trip created successfully!', 'success')
            return redirect(url_for('admin.get_admin_page'))
        except Exception as e:
            flash(f'Error creating trip: {str(e)}', 'error')
            return redirect(url_for('admin.new_trip'))

    return render_template('admin/trip_form.html', trip=None)

@admin.route('/admin/trips/<int:trip_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if request.method == 'POST':
        try:
            parsed_data = parse_trip_form(request.form)
            # Skip slug on edit - it's set only during creation
            parsed_data.pop('slug', None)
            for key, value in parsed_data.items():
                setattr(trip, key, value)
            db.session.commit()
            flash('Trip updated successfully!', 'success')
            return redirect(url_for('admin.get_admin_trips'))
        except Exception as e:
            flash(f'Error updating trip: {str(e)}', 'error')
            return redirect(url_for('admin.edit_trip', trip_id=trip_id))

    return render_template('admin/trip_form.html', trip=trip)

@admin.route('/admin/trips/<int:trip_id>/delete')
@admin_required
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    try:
        db.session.delete(trip)
        db.session.commit()
        flash('Trip deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting trip: {str(e)}', 'error')
    
    return redirect(url_for('admin.get_admin_trips'))

@admin.route('/admin/seasons')
@admin_required
def get_admin_seasons():
    seasons = Season.query.order_by(Season.start_date.desc()).all()
    return render_template('admin/seasons.html', seasons=seasons)

@admin.route('/admin/seasons/new', methods=['GET', 'POST'])
@admin_required
def new_season():
    if request.method == 'POST':
        is_valid, error_message, parsed_data = validate_season_form(request.form)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('admin/season_form.html', season=get_season_form_data(request.form))

        try:
            season = Season(**parsed_data)
            db.session.add(season)
            db.session.commit()
            flash('Season created successfully!', 'success')
            return redirect(url_for('admin.get_admin_seasons'))
        except Exception as e:
            flash(f'Error creating season: {str(e)}', 'error')
            return redirect(url_for('admin.new_season'))
    return render_template('admin/season_form.html', season=None)

@admin.route('/admin/seasons/<int:season_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_season(season_id):
    season = Season.query.get_or_404(season_id)
    if request.method == 'POST':
        is_valid, error_message, parsed_data = validate_season_form(request.form)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('admin/season_form.html', season=get_season_form_data(request.form))

        try:
            for key, value in parsed_data.items():
                setattr(season, key, value)
            db.session.commit()
            flash('Season updated successfully!', 'success')
            return redirect(url_for('admin.get_admin_seasons'))
        except Exception as e:
            flash(f'Error updating season: {str(e)}', 'error')
            return redirect(url_for('admin.edit_season', season_id=season_id))
    return render_template('admin/season_form.html', season=season)

@admin.route('/admin/seasons/<int:season_id>/delete')
@admin_required
def delete_season(season_id):
    season = Season.query.get_or_404(season_id)
    try:
        db.session.delete(season)
        db.session.commit()
        flash('Season deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting season: {str(e)}', 'error')
    return redirect(url_for('admin.get_admin_seasons'))


@admin.route('/admin/seasons/<int:season_id>/export')
@admin_required
def export_season_members(season_id):
    season = Season.query.get_or_404(season_id)
    results = (
        db.session.query(User, UserSeason)
        .join(UserSeason, User.id == UserSeason.user_id)
        .filter(UserSeason.season_id == season.id)
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)

    header = [
        'First Name',
        'Last Name',
        'Email',
        'Slack UID',
        'Status',
        'Notes',
        'Phone',
        'Address',
        'Date of Birth',
        'Pronouns',
        'Preferred Technique',
        'T-Shirt Size',
        'Ski Experience',
        'Emergency Contact Name',
        'Emergency Contact Relation',
        'Emergency Contact Phone',
        'Emergency Contact Email',
        'Registration Type',
        'Registration Date',
        'Payment Date',
        'Season Status',
    ]

    writer.writerow(header)
    for user, us in results:
        writer.writerow([
            user.first_name,
            user.last_name,
            user.email,
            user.slack_user.slack_uid if user.slack_user else '',
            user.status,
            user.notes or '',
            user.phone or '',
            user.address or '',
            user.date_of_birth or '',
            user.pronouns or '',
            user.preferred_technique or '',
            user.tshirt_size or '',
            user.ski_experience or '',
            user.emergency_contact_name or '',
            user.emergency_contact_relation or '',
            user.emergency_contact_phone or '',
            user.emergency_contact_email or '',
            us.registration_type,
            us.registration_date,
            us.payment_date or '',
            us.status,
        ])

    output.seek(0)
    filename = f"{season.name.replace(' ', '_')}_members.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@admin.route('/admin/users')
@admin_required
def get_admin_users():
    users = User.query.order_by(User.last_name, User.first_name).all()
    today = datetime.utcnow().date()
    
    active_season = Season.query.filter(
        Season.start_date <= today,
        Season.end_date >= today
    ).first()
    
    if active_season:
        current_season = active_season
    else:
        current_season = Season.query.filter(
            Season.start_date > today
        ).order_by(Season.start_date.asc()).first()
    
    user_season_map = {}
    if current_season:
        user_season_map = {
            us.user_id: us for us in UserSeason.query.filter_by(season_id=current_season.id).all()
        }
    
    return render_template('admin/users.html', users=users, user_season_map=user_season_map, current_season=current_season)

@admin.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    feedback = None
    # Fetch all UserSeason records for this user, joined with Season
    user_seasons = (
        db.session.query(UserSeason, Season)
        .join(Season, UserSeason.season_id == Season.id)
        .filter(UserSeason.user_id == user.id)
        .order_by(Season.start_date.desc())
        .all()
    )
    if request.method == 'POST':
        form_type = request.form.get('form_type', 'quick')
        if form_type == 'quick':
            user.email = request.form.get('email')
            user.status = request.form.get('status')
            try:
                db.session.commit()
                flash('User email/status updated!', 'success')
                feedback = 'quick'
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating user: {str(e)}', 'error')
        elif form_type == 'full':
            def update_if_present(field, value):
                if value is not None and value != '':
                    setattr(user, field, value)
            update_if_present('first_name', request.form.get('first_name'))
            update_if_present('last_name', request.form.get('last_name'))
            update_if_present('email', request.form.get('email'))
            update_if_present('pronouns', request.form.get('pronouns'))
            update_if_present('phone', request.form.get('phone'))
            update_if_present('address', request.form.get('address'))
            dob = request.form.get('date_of_birth')
            if dob:
                try:
                    user.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                except Exception:
                    flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'error')
            update_if_present('preferred_technique', request.form.get('preferred_technique'))
            update_if_present('tshirt_size', request.form.get('tshirt_size'))
            update_if_present('ski_experience', request.form.get('ski_experience'))
            update_if_present('emergency_contact_name', request.form.get('emergency_contact_name'))
            update_if_present('emergency_contact_relation', request.form.get('emergency_contact_relation'))
            update_if_present('emergency_contact_phone', request.form.get('emergency_contact_phone'))
            update_if_present('emergency_contact_email', request.form.get('emergency_contact_email'))
            update_if_present('notes', request.form.get('notes'))
            update_if_present('status', request.form.get('status'))
            slack_uid = request.form.get('slack_uid')
            if slack_uid is not None and slack_uid != '':
                if user.slack_user:
                    user.slack_user.slack_uid = slack_uid
                else:
                    from ..models import SlackUser
                    slack_user = SlackUser(slack_uid=slack_uid, full_name=user.full_name, email=user.email)
                    db.session.add(slack_user)
                    db.session.flush()
                    user.slack_user_id = slack_user.id
            try:
                db.session.commit()
                flash('User updated successfully!', 'success')
                feedback = 'full'
                return redirect(url_for('admin.edit_user', user_id=user.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating user: {str(e)}', 'error')
    return render_template('admin/user_edit.html', user=user, feedback=feedback, user_seasons=user_seasons)
