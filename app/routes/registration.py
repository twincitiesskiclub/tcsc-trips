from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from ..models import db, Season, UserSeason, User, Payment
from ..constants import DATE_FORMAT, UserStatus, UserSeasonStatus
from datetime import datetime
from ..errors import flash_error, flash_info
from ..utils import get_current_times, normalize_email, format_datetime_central, today_central, validate_registration_form

registration = Blueprint('registration', __name__)

@registration.route('/seasons')
def seasons_listing():
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
        returning_open = season.is_returning_open(now)
        new_open = season.is_new_open(now)
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
    times = get_current_times()
    current_time = times['central']  # Use localized time for potential display
    now_utc = times['utc']  # Use UTC for comparisons

    if request.method == 'POST':
        try:
            form = request.form
            email = normalize_email(form['email'])
            user = User.get_by_email(email)

            # Get payment_intent_id for coordination with webhook
            payment_intent_id = form.get('payment_intent_id')
            existing_payment = None
            if payment_intent_id:
                existing_payment = Payment.get_by_payment_intent(payment_intent_id)

            # Determine member_type from backend only BEFORE checking dates
            # Check user existence first
            is_returning = bool(user and getattr(user, 'is_returning', False))

            # Check if registration window is open for this user type
            member_type_str = 'returning' if is_returning else 'new'
            if not season.is_open_for(member_type_str, now_utc):
                status_msg = "returning members" if is_returning else "new members"
                flash_error(f'Sorry, the registration window for {status_msg} is currently closed.')
                return redirect(url_for('registration.season_register', season_id=season_id))

            client_claimed_status = form['status']
            # Check consistency between claimed status and actual status
            if client_claimed_status == 'returning_former' and not is_returning:
                flash_error('Your email is not associated with a returning member. Please register as a New Member.')
                return redirect(url_for('registration.season_register', season_id=season_id))
            if client_claimed_status == 'new' and is_returning:
                flash_error('Your email is associated with a returning member. Please register as a Returning Member.')
                return redirect(url_for('registration.season_register', season_id=season_id))
            
            # --- Proceed with form processing only if checks pass ---
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
                    user_fields['date_of_birth'] = datetime.strptime(dob_str, DATE_FORMAT).date()
                except ValueError as e:
                    flash_error('Invalid date format for Date of Birth. Please use YYYY-MM-DD.')
                    return redirect(url_for('registration.season_register', season_id=season_id))

            # Validate all form fields before proceeding
            is_valid, validation_errors = validate_registration_form(form, user_fields.get('date_of_birth'))
            if not is_valid:
                for error in validation_errors:
                    flash_error(error)
                return redirect(url_for('registration.season_register', season_id=season_id))

            if user:
                for k, v in user_fields.items():
                    setattr(user, k, v)
            else:
                user = User(email=email, status=UserStatus.PENDING, **user_fields)
                db.session.add(user)
                db.session.flush()  # get user.id

            # Link payment to user if webhook created it before form submission
            if existing_payment and not existing_payment.user_id:
                existing_payment.user_id = user.id

            # Determine member_type from backend only
            is_returning = user.is_returning
            client_claimed_status = form['status']
            if client_claimed_status == 'returning_former' and not is_returning:
                flash_error('You have no active past membership; register as New.')
                return redirect(url_for('registration.season_register', season_id=season_id))
            member_type = 'returning' if is_returning else 'new'

            # Find or create UserSeason for this user and season
            # Note: Webhook may have already created this record. We check first to avoid
            # duplicates. If webhook created it, we just update the fields.
            user_season = UserSeason.get_for_user_season(user.id, season.id)
            if not user_season:
                user_season = UserSeason(
                    user_id=user.id,
                    season_id=season.id,
                    registration_type=member_type,
                    registration_date=today_central(),
                    status=UserSeasonStatus.ACTIVE if is_returning else UserSeasonStatus.PENDING_LOTTERY
                )
                db.session.add(user_season)
            else:
                user_season.registration_type = member_type
                user_season.registration_date = current_time.date()
                user_season.status = UserSeasonStatus.ACTIVE if is_returning else UserSeasonStatus.PENDING_LOTTERY

            db.session.commit()
            # flash('Registration submitted successfully!', 'success')
            payment_hold = not is_returning
            return render_template('season_success.html', season=season, payment_hold=payment_hold)
        except Exception as e:
            flash_error(f'Error submitting registration: {str(e)}')
            return redirect(url_for('registration.season_register', season_id=season_id))

    # --- GET Request Handling ---
    if not season.is_any_registration_open(now_utc):
        # Determine the appropriate message based on timing
        message = "Registration is currently closed for this season."
        # Check timezone handling for accurate display
        if season.returning_start and now_utc < season.returning_start:
            message = f"Registration for returning members opens on {format_datetime_central(season.returning_start)}."
        elif season.new_start and now_utc < season.new_start:
            # Check if returning window might still be open or hasn't started
            if not (season.returning_start and season.returning_start <= now_utc):
                message = f"Registration for new members opens on {format_datetime_central(season.new_start)}."

        flash_info(message)
        return redirect(url_for('main.get_home_page')) # Redirect to home page which shows status

    # If GET request and registration is open, render the form
    return render_template('season_register.html', season=season)

@registration.route('/seasons/<int:season_id>')
def season_detail(season_id):
    season = Season.query.get_or_404(season_id)
    now_utc = datetime.utcnow()

    # Check if registration is currently open for returning or new members
    is_registration_open = season.is_any_registration_open(now_utc)

    # # --- Redirect if registration is NOT open --- Currently allow viewing details even if closed
    # if not is_registration_open:
    #     message = "Registration is currently closed for this season."
    #     if season.returning_start and now_utc < season.returning_start:
    #         message = f"Registration for returning members opens on {season.returning_start.strftime('%b %d, %Y %I:%M %p UTC')}."
    #     elif season.new_start and now_utc < season.new_start:
    #         if not (season.returning_start and season.returning_start <= now_utc):
    #              message = f"Registration for new members opens on {season.new_start.strftime('%b %d, %Y %I:%M %p UTC')}."
    #     flash(message, 'info')
    #     return redirect(url_for('main.get_home_page'))

    return render_template('season_detail.html', 
                           season=season, 
                           now=now_utc, 
                           is_registration_open=is_registration_open)

@registration.route('/api/is_returning_member', methods=['POST'])
def api_is_returning_member():
    data = request.get_json()
    email = normalize_email(data.get('email', ''))
    user = User.get_by_email(email)
    is_returning = bool(user and getattr(user, 'is_returning', False))
    return jsonify({'is_returning': is_returning}) 