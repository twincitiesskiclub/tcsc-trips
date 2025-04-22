from flask import Blueprint, render_template, request, flash, redirect, url_for
from ..models import db, Season, UserSeason, User
from datetime import datetime
import pytz

registration = Blueprint('registration', __name__)

@registration.route('/seasons')
def seasons_listing():
    from datetime import datetime
    now = datetime.utcnow()
    # Find the next or current season by registration window
    season = (
        Season.query
        .filter(
            (Season.returning_start != None) | (Season.new_start != None)
        )
        .order_by(Season.start_date.asc())
        .first()
    )
    registration_status = None
    registration_message = None
    can_register = False
    if season:
        # Determine if registration is open for returning or new
        returning_open = season.returning_start and season.returning_start <= now <= season.returning_end
        new_open = season.new_start and season.new_start <= now <= season.new_end
        if returning_open or new_open:
            can_register = True
        if returning_open and not new_open:
            registration_status = 'returning_only'
            registration_message = f"Registration is open for returning members until {season.returning_end.strftime('%b %d, %Y %I:%M %p')}!"
        elif new_open and not returning_open:
            registration_status = 'new_only'
            registration_message = f"Registration is open for new members until {season.new_end.strftime('%b %d, %Y %I:%M %p')}!"
        elif returning_open and new_open:
            registration_status = 'both_open'
            registration_message = f"Registration is open for all members!"
        else:
            # Not open yet, show next opening
            if season.returning_start and now < season.returning_start:
                registration_message = f"Registration for returning members opens on {season.returning_start.strftime('%b %d, %Y %I:%M %p')}"
            elif season.new_start and now < season.new_start:
                registration_message = f"Registration for new members opens on {season.new_start.strftime('%b %d, %Y %I:%M %p')}"
            else:
                registration_message = "Registration is currently closed."
    else:
        registration_message = "No upcoming seasons available. Please check back soon!"
    return render_template('seasons.html', season=season, can_register=can_register, registration_message=registration_message)

@registration.route('/seasons/<int:season_id>/register', methods=['GET', 'POST'])
def season_register(season_id):
    season = Season.query.get_or_404(season_id)
    central = pytz.timezone('America/Chicago')
    current_time = datetime.now(central)

    if request.method == 'POST':
        try:
            form = request.form
            email = form['email'].strip().lower()
            user = User.query.filter_by(email=email).one_or_none()

            # Collect all personal fields from form
            user_fields = dict(
                first_name=form['firstName'],
                last_name=form['lastName'],
                pronouns=form.get('pronouns'),
                date_of_birth=None,  # will set below
                phone=form['phone'],
                address=form['address'],
                preferred_technique=form.get('technique'),
                tshirt_size=form['tshirtSize'],
                ski_experience=form.get('experience'),
                emergency_contact_name=form['emergencyName'],
                emergency_contact_relation=form['emergencyRelation'],
                emergency_contact_phone=form['emergencyPhone'],
                emergency_contact_email=form['emergencyEmail'],
            )
            # Convert dob string to date object
            dob_str = form['dob']
            if dob_str:
                try:
                    user_fields['date_of_birth'] = datetime.strptime(dob_str, '%Y-%m-%d').date()
                except Exception:
                    flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'error')
                    return redirect(url_for('registration.season_register', season_id=season_id))

            if user:
                for k, v in user_fields.items():
                    setattr(user, k, v)
            else:
                user = User(email=email, status='pending', **user_fields)
                db.session.add(user)
                db.session.flush()  # get user.id

            # Determine member_type from backend only
            is_returning = user.is_returning
            client_claimed_status = form['status']
            if client_claimed_status == 'returning_former' and not is_returning:
                flash('You have no active past membership; register as New.', 'error')
                return redirect(url_for('registration.season_register', season_id=season_id))
            member_type = 'returning' if is_returning else 'new'

            # Find or create UserSeason for this user and season
            user_season = UserSeason.query.filter_by(user_id=user.id, season_id=season.id).one_or_none()
            if not user_season:
                user_season = UserSeason(
                    user_id=user.id,
                    season_id=season.id,
                    registration_type=member_type,
                    registration_date=current_time.date(),
                    status='ACTIVE' if is_returning else 'PENDING_LOTTERY'
                )
                db.session.add(user_season)
            else:
                user_season.registration_type = member_type
                user_season.registration_date = current_time.date()
                user_season.status = 'ACTIVE' if is_returning else 'PENDING_LOTTERY'

            db.session.commit()
            flash('Registration submitted successfully!', 'success')
            return redirect(url_for('main.get_home_page'))
        except Exception as e:
            flash(f'Error submitting registration: {str(e)}', 'error')
            return redirect(url_for('registration.season_register', season_id=season_id))

    return render_template('season_register.html', season=season)

@registration.route('/seasons/<int:season_id>')
def season_detail(season_id):
    from datetime import datetime
    season = Season.query.get_or_404(season_id)
    return render_template('season_detail.html', season=season, now=datetime.utcnow())

@registration.route('/api/is_returning_member', methods=['POST'])
def api_is_returning_member():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).one_or_none()
    is_returning = bool(user and getattr(user, 'is_returning', False))
    return {'is_returning': is_returning} 