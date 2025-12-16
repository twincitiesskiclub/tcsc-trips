from flask import Blueprint, render_template, jsonify, request, redirect, url_for, Response, session
from sqlalchemy import func
from ..auth import admin_required
from ..models import db, Payment, Trip, Season, User, UserSeason, SlackUser, SocialEvent
from ..constants import DATE_FORMAT, DATETIME_FORMAT, MIN_PRICE_CENTS, CENTS_PER_DOLLAR
from ..errors import flash_error, flash_success
from datetime import datetime, timedelta
import csv
from io import StringIO

admin = Blueprint('admin', __name__)

# Users authorized to view payment amounts
FINANCE_AUTHORIZED_EMAILS = [
    'admin@twincitiesskiclub.org',
    'finance@twincitiesskiclub.org'
]


def is_finance_authorized():
    """Check if the current user is authorized to view payment amounts."""
    user = session.get('user', {})
    return user.get('email', '').lower() in [e.lower() for e in FINANCE_AUTHORIZED_EMAILS]


def delete_entity(model, entity_id, entity_name, redirect_endpoint):
    """Generic delete handler for admin CRUD operations.

    Args:
        model: SQLAlchemy model class
        entity_id: ID of the entity to delete
        entity_name: Human-readable name for flash messages (e.g., 'Trip', 'Season')
        redirect_endpoint: Flask endpoint to redirect to after deletion

    Returns:
        Flask redirect response
    """
    entity = model.query.get_or_404(entity_id)
    try:
        db.session.delete(entity)
        db.session.commit()
        flash_success(f'{entity_name} deleted successfully!')
    except Exception as e:
        flash_error(f'Error deleting {entity_name.lower()}: {str(e)}')
    return redirect(url_for(redirect_endpoint))


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


def parse_social_event_form(form):
    """Parse and validate social event form data.

    Returns:
        dict: Parsed social event data ready for model creation/update
    """
    return {
        'slug': form['slug'],
        'name': form['name'],
        'location': form['location'],
        'max_participants': int(form['max_participants']),
        'event_date': datetime.strptime(form['event_date'], DATETIME_FORMAT),
        'signup_start': datetime.strptime(form['signup_start'], DATETIME_FORMAT),
        'signup_end': datetime.strptime(form['signup_end'], DATETIME_FORMAT),
        'price': int(float(form['price']) * CENTS_PER_DOLLAR),
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
    return render_template('admin/payments.html')


@admin.route('/admin/payments/data')
@admin_required
def get_payments_data():
    """Return all payments as JSON for the Tabulator data grid."""
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    can_view_amounts = is_finance_authorized()

    payments_data = []
    for payment in payments:
        # Get the associated trip, season, or social event name
        for_name = '-'
        if payment.payment_type == 'trip' and payment.trip:
            for_name = payment.trip.name
        elif payment.payment_type == 'season' and payment.season:
            for_name = payment.season.name
        elif payment.payment_type == 'social_event' and payment.social_event:
            for_name = payment.social_event.name

        # Map status to display status
        display_status = {
            'requires_payment_method': 'pending',
            'requires_confirmation': 'pending',
            'requires_action': 'pending',
            'requires_capture': 'pending',
            'processing': 'processing',
            'succeeded': 'success',
            'canceled': 'canceled',
            'refunded': 'refunded'
        }.get(payment.status, 'unknown')

        payments_data.append({
            'id': payment.id,
            'name': payment.name,
            'email': payment.email,
            'payment_type': payment.payment_type,
            'for_name': for_name,
            'amount': payment.amount / 100 if can_view_amounts else None,
            'status': payment.status,
            'display_status': display_status,
            'created_at': payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else '',
            'payment_intent_id': payment.payment_intent_id,
        })

    return jsonify({'payments': payments_data, 'can_view_amounts': can_view_amounts})

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
            flash_success('Trip created successfully!')
            return redirect(url_for('admin.get_admin_page'))
        except Exception as e:
            flash_error(f'Error creating trip: {str(e)}')
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
            flash_success('Trip updated successfully!')
            return redirect(url_for('admin.get_admin_trips'))
        except Exception as e:
            flash_error(f'Error updating trip: {str(e)}')
            return redirect(url_for('admin.edit_trip', trip_id=trip_id))

    return render_template('admin/trip_form.html', trip=trip)

@admin.route('/admin/trips/<int:trip_id>/delete')
@admin_required
def delete_trip(trip_id):
    return delete_entity(Trip, trip_id, 'Trip', 'admin.get_admin_trips')

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
            flash_error(error_message)
            return render_template('admin/season_form.html', season=get_season_form_data(request.form))

        try:
            season = Season(**parsed_data)
            db.session.add(season)
            db.session.commit()
            flash_success('Season created successfully!')
            return redirect(url_for('admin.get_admin_seasons'))
        except Exception as e:
            flash_error(f'Error creating season: {str(e)}')
            return redirect(url_for('admin.new_season'))
    return render_template('admin/season_form.html', season=None)

@admin.route('/admin/seasons/<int:season_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_season(season_id):
    season = Season.query.get_or_404(season_id)
    if request.method == 'POST':
        is_valid, error_message, parsed_data = validate_season_form(request.form)
        if not is_valid:
            flash_error(error_message)
            return render_template('admin/season_form.html', season=get_season_form_data(request.form))

        try:
            for key, value in parsed_data.items():
                setattr(season, key, value)
            db.session.commit()
            flash_success('Season updated successfully!')
            return redirect(url_for('admin.get_admin_seasons'))
        except Exception as e:
            flash_error(f'Error updating season: {str(e)}')
            return redirect(url_for('admin.edit_season', season_id=season_id))
    return render_template('admin/season_form.html', season=season)

@admin.route('/admin/seasons/<int:season_id>/delete')
@admin_required
def delete_season(season_id):
    return delete_entity(Season, season_id, 'Season', 'admin.get_admin_seasons')


# Social Events CRUD
@admin.route('/admin/social-events')
@admin_required
def get_admin_social_events():
    social_events = SocialEvent.query.order_by(SocialEvent.event_date).all()
    return render_template('admin/social_events.html', social_events=social_events)


@admin.route('/admin/social-events/new', methods=['GET', 'POST'])
@admin_required
def new_social_event():
    if request.method == 'POST':
        try:
            social_event = SocialEvent(**parse_social_event_form(request.form))
            db.session.add(social_event)
            db.session.commit()
            flash_success('Social event created successfully!')
            return redirect(url_for('admin.get_admin_social_events'))
        except Exception as e:
            flash_error(f'Error creating social event: {str(e)}')
            return redirect(url_for('admin.new_social_event'))

    return render_template('admin/social_event_form.html', social_event=None)


@admin.route('/admin/social-events/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_social_event(event_id):
    social_event = SocialEvent.query.get_or_404(event_id)

    if request.method == 'POST':
        try:
            parsed_data = parse_social_event_form(request.form)
            # Skip slug on edit - it's set only during creation
            parsed_data.pop('slug', None)
            for key, value in parsed_data.items():
                setattr(social_event, key, value)
            db.session.commit()
            flash_success('Social event updated successfully!')
            return redirect(url_for('admin.get_admin_social_events'))
        except Exception as e:
            flash_error(f'Error updating social event: {str(e)}')
            return redirect(url_for('admin.edit_social_event', event_id=event_id))

    return render_template('admin/social_event_form.html', social_event=social_event)


@admin.route('/admin/social-events/<int:event_id>/delete')
@admin_required
def delete_social_event(event_id):
    return delete_entity(SocialEvent, event_id, 'Social Event', 'admin.get_admin_social_events')


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

def get_current_season():
    """Get the current or next upcoming season."""
    today = datetime.utcnow().date()
    active_season = Season.query.filter(
        Season.start_date <= today,
        Season.end_date >= today
    ).first()

    if active_season:
        return active_season
    return Season.query.filter(
        Season.start_date > today
    ).order_by(Season.start_date.asc()).first()


@admin.route('/admin/users')
@admin_required
def get_admin_users():
    current_season = get_current_season()
    all_seasons = Season.query.order_by(Season.start_date.desc()).all()
    return render_template('admin/users.html', current_season=current_season, all_seasons=all_seasons)


@admin.route('/admin/users/data')
@admin_required
def get_users_data():
    """Return all users as JSON for the data grid."""
    users = User.query.order_by(User.last_name, User.first_name).all()
    current_season = get_current_season()
    all_seasons = Season.query.order_by(Season.start_date.desc()).all()

    # Build a map of user_id -> {season_id: status} for all seasons
    all_user_seasons = UserSeason.query.all()
    user_seasons_map = {}
    for us in all_user_seasons:
        if us.user_id not in user_seasons_map:
            user_seasons_map[us.user_id] = {}
        user_seasons_map[us.user_id][us.season_id] = us.status

    # Build a map of user_id -> {trip_count, total_paid} from successful payments
    payment_stats = db.session.query(
        Payment.user_id,
        func.count(func.distinct(Payment.trip_id)).label('trip_count'),
        func.sum(Payment.amount).label('total_cents')
    ).filter(
        Payment.user_id != None,
        Payment.status == 'succeeded'
    ).group_by(Payment.user_id).all()

    payment_map = {uid: {'trips': tc, 'total': tot or 0}
                   for uid, tc, tot in payment_stats}

    users_data = []
    for user in users:
        user_season_data = user_seasons_map.get(user.id, {})
        current_season_status = user_season_data.get(current_season.id, '') if current_season else ''
        user_payment_stats = payment_map.get(user.id, {'trips': 0, 'total': 0})

        users_data.append({
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'email': user.email,
            'phone': user.phone or '',
            'address': user.address or '',
            'status': user.status,
            'pronouns': user.pronouns or '',
            'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else '',
            'preferred_technique': user.preferred_technique or '',
            'tshirt_size': user.tshirt_size or '',
            'ski_experience': user.ski_experience or '',
            'emergency_contact_name': user.emergency_contact_name or '',
            'emergency_contact_phone': user.emergency_contact_phone or '',
            'emergency_contact_email': user.emergency_contact_email or '',
            'emergency_contact_relation': user.emergency_contact_relation or '',
            'slack_uid': user.slack_user.slack_uid if user.slack_user else '',
            'season_status': current_season_status,
            'seasons': user_season_data,  # {season_id: status} for all seasons
            'is_returning': user.is_returning,
            'created_at': user.created_at.isoformat() if user.created_at else '',
            'trip_count': user_payment_stats['trips'],
            'total_paid': user_payment_stats['total'] / 100,  # Convert cents to dollars
        })

    return jsonify({
        'users': users_data,
        'current_season': {'id': current_season.id, 'name': current_season.name} if current_season else None,
        'seasons': [{'id': s.id, 'name': s.name} for s in all_seasons]
    })


@admin.route('/admin/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    """Display member detail page with payment history."""
    user = User.query.get_or_404(user_id)

    # Get all payments for this user
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.created_at.desc()).all()

    # Get all season registrations
    user_seasons = (
        db.session.query(UserSeason, Season)
        .join(Season, UserSeason.season_id == Season.id)
        .filter(UserSeason.user_id == user.id)
        .order_by(Season.start_date.desc())
        .all()
    )

    # Build trip registrations from payments (grouped by trip)
    trip_registrations = {}
    for payment in payments:
        if payment.trip_id not in trip_registrations:
            trip_registrations[payment.trip_id] = {
                'trip': payment.trip,
                'total_paid': 0,
                'payment_count': 0,
                'latest_status': payment.status,
                'latest_date': payment.created_at,
            }
        if payment.status == 'succeeded':
            trip_registrations[payment.trip_id]['total_paid'] += payment.amount
        trip_registrations[payment.trip_id]['payment_count'] += 1

    # Sort by trip start date descending
    sorted_trips = sorted(
        trip_registrations.values(),
        key=lambda x: x['trip'].start_date if x['trip'].start_date else datetime.min,
        reverse=True
    )

    return render_template('admin/user_detail.html',
                          user=user,
                          payments=payments,
                          user_seasons=user_seasons,
                          trip_registrations=sorted_trips)

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
                flash_success('User email/status updated!')
                feedback = 'quick'
            except Exception as e:
                db.session.rollback()
                flash_error(f'Error updating user: {str(e)}')
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
                    user.date_of_birth = datetime.strptime(dob, DATE_FORMAT).date()
                except ValueError as e:
                    flash_error('Invalid date format for Date of Birth. Please use YYYY-MM-DD.')
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
                    slack_user = SlackUser(slack_uid=slack_uid, full_name=user.full_name, email=user.email)
                    db.session.add(slack_user)
                    db.session.flush()
                    user.slack_user_id = slack_user.id
            try:
                db.session.commit()
                flash_success('User updated successfully!')
                feedback = 'full'
                return redirect(url_for('admin.edit_user', user_id=user.id))
            except Exception as e:
                db.session.rollback()
                flash_error(f'Error updating user: {str(e)}')
    return render_template('admin/user_edit.html', user=user, feedback=feedback, user_seasons=user_seasons)
