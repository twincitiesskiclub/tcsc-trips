from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from ..auth import admin_required
from ..models import db, Payment, Trip, Season, User, UserSeason
from datetime import datetime, timedelta

admin = Blueprint('admin', __name__)

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
            trip = Trip(
                slug=request.form['slug'],
                name=request.form['name'],
                destination=request.form['destination'],
                max_participants_standard=int(request.form['max_participants_standard']),
                max_participants_extra=int(request.form['max_participants_extra']),
                start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
                end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d'),
                signup_start=datetime.strptime(request.form['signup_start'], '%Y-%m-%dT%H:%M'),
                signup_end=datetime.strptime(request.form['signup_end'], '%Y-%m-%dT%H:%M'),
                price_low=int(float(request.form['price_low']) * 100),  # Convert to cents
                price_high=int(float(request.form['price_high']) * 100),  # Convert to cents
                description=request.form['description'],
                status=request.form['status']
            )
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
            trip.name = request.form['name']
            trip.destination = request.form['destination']
            trip.max_participants_standard = int(request.form['max_participants_standard'])
            trip.max_participants_extra = int(request.form['max_participants_extra'])
            trip.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            trip.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
            trip.signup_start = datetime.strptime(request.form['signup_start'], '%Y-%m-%dT%H:%M')
            trip.signup_end = datetime.strptime(request.form['signup_end'], '%Y-%m-%dT%H:%M')
            trip.price_low = int(float(request.form['price_low']) * 100)
            trip.price_high = int(float(request.form['price_high']) * 100)
            trip.description = request.form['description']
            trip.status = request.form['status']
            
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
        try:
            year = int(request.form['year'])
            season_type = request.form['season_type']
            name = f"{year} {season_type.title()}"
            price_cents = int(float(request.form['price_cents']) * 100) if request.form.get('price_cents') else None
            if price_cents is None or price_cents < 100:
                flash('Price must be at least $1.00 (100 cents).', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            if start_date < week_ago or end_date < week_ago:
                flash('Season start and end dates cannot be more than a week in the past.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            returning_start = datetime.strptime(request.form['returning_start'], '%Y-%m-%dT%H:%M') if request.form.get('returning_start') else None
            returning_end = datetime.strptime(request.form['returning_end'], '%Y-%m-%dT%H:%M') if request.form.get('returning_end') else None
            new_start = datetime.strptime(request.form['new_start'], '%Y-%m-%dT%H:%M') if request.form.get('new_start') else None
            new_end = datetime.strptime(request.form['new_end'], '%Y-%m-%dT%H:%M') if request.form.get('new_end') else None
            # Registration windows must be before the season start date
            if (returning_start and returning_start >= start_date) or (returning_end and returning_end >= start_date):
                flash('Returning registration window must be before the season start date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (new_start and new_start >= start_date) or (new_end and new_end >= start_date):
                flash('New registration window must be before the season start date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            # Start dates must be before end dates
            if start_date >= end_date:
                flash('Season start date must be before end date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (returning_start and returning_end and returning_start >= returning_end):
                flash('Returning registration start must be before end.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (new_start and new_end and new_start >= new_end):
                flash('New registration start must be before end.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            season = Season(
                name=name,
                season_type=season_type,
                year=year,
                start_date=start_date,
                end_date=end_date,
                price_cents=price_cents,
                returning_start=returning_start,
                returning_end=returning_end,
                new_start=new_start,
                new_end=new_end,
                registration_limit=int(request.form['registration_limit']) if request.form.get('registration_limit') else None,
                description=request.form.get('description')
            )
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
        try:
            year = int(request.form['year'])
            season_type = request.form['season_type']
            price_cents = int(float(request.form['price_cents']) * 100) if request.form.get('price_cents') else None
            if price_cents is None or price_cents < 100:
                flash('Price must be at least $1.00 (100 cents).', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            if start_date < week_ago or end_date < week_ago:
                flash('Season start and end dates cannot be more than a week in the past.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            returning_start = datetime.strptime(request.form['returning_start'], '%Y-%m-%dT%H:%M') if request.form.get('returning_start') else None
            returning_end = datetime.strptime(request.form['returning_end'], '%Y-%m-%dT%H:%M') if request.form.get('returning_end') else None
            new_start = datetime.strptime(request.form['new_start'], '%Y-%m-%dT%H:%M') if request.form.get('new_start') else None
            new_end = datetime.strptime(request.form['new_end'], '%Y-%m-%dT%H:%M') if request.form.get('new_end') else None
            # Registration windows must be before the season start date
            if (returning_start and returning_start >= start_date) or (returning_end and returning_end >= start_date):
                flash('Returning registration window must be before the season start date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (new_start and new_start >= start_date) or (new_end and new_end >= start_date):
                flash('New registration window must be before the season start date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            # Start dates must be before end dates
            if start_date >= end_date:
                flash('Season start date must be before end date.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (returning_start and returning_end and returning_start >= returning_end):
                flash('Returning registration start must be before end.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            if (new_start and new_end and new_start >= new_end):
                flash('New registration start must be before end.', 'error')
                form_data = dict(request.form)
                form_data['price_cents'] = request.form.get('price_cents')
                return render_template('admin/season_form.html', season=form_data)
            season.name = f"{year} {season_type.title()}"
            season.season_type = season_type
            season.year = year
            season.start_date = start_date
            season.end_date = end_date
            season.price_cents = price_cents
            season.returning_start = returning_start
            season.returning_end = returning_end
            season.new_start = new_start
            season.new_end = new_end
            season.registration_limit = int(request.form['registration_limit']) if request.form.get('registration_limit') else None
            season.description = request.form.get('description')
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

@admin.route('/admin/users')
@admin_required
def get_admin_users():
    users = User.query.order_by(User.last_name, User.first_name).all()
    # Optionally, get the current season for per-season status
    current_season = Season.query.order_by(Season.start_date.desc()).first()
    user_season_map = {}
    if current_season:
        user_season_map = {
            us.user_id: us for us in UserSeason.query.filter_by(season_id=current_season.id).all()
        }
    return render_template('admin/users.html', users=users, user_season_map=user_season_map, current_season=current_season)

@admin.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    from datetime import datetime
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