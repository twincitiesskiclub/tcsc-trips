from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from ..models import db, Season, UserSeason, User, Payment
from ..constants import DATE_FORMAT, UserStatus, UserSeasonStatus
from datetime import datetime
from ..errors import flash_error, flash_info
from ..utils import (get_current_times, normalize_email, normalize_phone_e164,
                     format_phone_display, format_datetime_central,
                     today_central, validate_registration_form,
                     validate_volunteer_selections)
from ..verify.service import get_verified_identity, clear_verified_identity
from ..notifications.sms import send_sms
from ..seasons.resolution import (resolve_registration_step, WIZARD_RETURNING,
                                  ALREADY_REGISTERED)
from .. import late_link

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

    invite_token = request.args.get('invite')
    invite_payload = late_link.verify(invite_token) if invite_token else None
    invite_season_match = (
        invite_payload is not None
        and invite_payload.get('season_id') == season_id
    )

    if request.method == 'POST':
        try:
            form = request.form
            email = normalize_email(form['email'])

            # Invite-token short-circuit happens before any verification
            # concerns: a late-registration link for someone already
            # registered bounces immediately, regardless of session state.
            if invite_token:
                invite_check_user = User.get_by_email(email)
                if invite_check_user is not None:
                    existing_us = UserSeason.get_for_user_season(invite_check_user.id, season.id)
                    if existing_us and existing_us.status in (
                            UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY):
                        flash_error("This link has already been used. You're "
                                    "already registered for this season.")
                        return redirect(url_for('registration.season_register',
                                                season_id=season_id))

            identity = get_verified_identity()
            verified_user = None
            if identity and identity.get('user_id'):
                verified_user = User.query.get(identity['user_id'])

            continue_unverified = form.get('continue_unverified') == '1'
            if identity is None and not continue_unverified:
                # Session expired or the member skipped step 0 entirely.
                flash_error('Your verification expired. Please verify your '
                            'number again. Your answers are saved.')
                return redirect(url_for('registration.season_register',
                                        season_id=season_id))

            # Disclaimed identity: someone who verified into account A but
            # then took an unverified escape hatch with a DIFFERENT email
            # (the "Not [name]?" flow) has renounced that account link. Drop
            # it so nothing below binds to A's row, pricing, or capture
            # treatment. The identity dict itself is kept: the phone was
            # genuinely verified, so phone_e164/phone_verified_at stamping
            # below still applies to whichever row this POST resolves to.
            identity_disclaimed = (
                continue_unverified
                and verified_user is not None
                and email != normalize_email(verified_user.email)
            )
            disclaimed_name = None
            disclaimed_id = None
            if identity_disclaimed:
                disclaimed_name = verified_user.full_name
                disclaimed_id = verified_user.id
                verified_user = None

            if verified_user is not None:
                user = verified_user
                if email != user.email and User.get_by_email(email):
                    flash_error('That email already belongs to another '
                                'member. Please use a different one.')
                    return redirect(url_for('registration.season_register',
                                            season_id=season_id))
            else:
                user = None
                existing = User.get_by_email(email)
                if existing is not None:
                    if continue_unverified:
                        # Flagged path: reuse the row, admin will review.
                        user = existing
                    else:
                        flash_error('That email already has a member account. '
                                    'Go back and verify with this email, or '
                                    'choose "Continue anyway" if you can no '
                                    'longer receive mail there.')
                        return redirect(url_for('registration.season_register',
                                                season_id=season_id))

            # needs_review is about account-MATCH confidence, computed from
            # pre-creation state. review_note says which of the three ways
            # it went wrong so the admin page does not have to guess.
            review_note = None
            if identity is None:
                review_note = "no verified phone"
            elif identity_disclaimed:
                review_note = f"claims not to be {disclaimed_name} (id {disclaimed_id})"[:255]
            elif user is not None and verified_user is None:
                review_note = f"claimed existing account {user.email}, email unverified"[:255]
            needs_review = review_note is not None

            # Get payment_intent_id for coordination with webhook
            payment_intent_id = form.get('payment_intent_id')
            if not payment_intent_id:
                flash_error('Payment is required to complete registration.')
                return redirect(url_for('registration.season_register', season_id=season_id))
            existing_payment = Payment.get_by_payment_intent(payment_intent_id)

            # One rule, one place. The POST must not be able to disagree
            # with the screen the member was just looking at.
            #
            # The session dict still carries the disclaimed user_id, so it
            # has to be scrubbed before the resolver sees it. Otherwise
            # someone who just said "I'm not Jane" would be priced as Jane.
            resolver_identity = identity
            if identity is not None and identity_disclaimed:
                resolver_identity = {**identity, 'user_id': None}
            outcome, _ = resolve_registration_step(
                resolver_identity, season, now_utc,
                invite_payload if invite_season_match else None)
            if outcome == ALREADY_REGISTERED:
                flash_error("You're already registered for this season.")
                return redirect(url_for('registration.season_register',
                                        season_id=season_id))
            is_returning = (outcome == WIZARD_RETURNING)

            # Check if registration window is open for this user type
            member_type_str = 'returning' if is_returning else 'new'
            invite_valid_for_email = (
                invite_season_match
                and invite_payload.get('email') == email
            )
            if invite_token and not invite_valid_for_email:
                # Token present but signature/expiry/email mismatch — explain why.
                if invite_payload is None:
                    flash_error('This link is invalid or has expired. Please ask an admin for a new one.')
                elif not invite_season_match:
                    flash_error('This link is for a different season.')
                else:
                    flash_error('This link was issued for a different email.')
                return redirect(url_for('registration.season_register', season_id=season_id, invite=invite_token))
            if not invite_valid_for_email and not season.is_open_for(member_type_str, now_utc):
                status_msg = "returning members" if is_returning else "new members"
                flash_error(f'Sorry, the registration window for {status_msg} is currently closed.')
                return redirect(url_for('registration.season_register', season_id=season_id))

            # --- Proceed with form processing only if checks pass ---
            # Collect all personal fields from form
            user_fields = dict(
                first_name=form['firstName'],
                last_name=form['lastName'],
                pronouns=form.get('pronouns'),
                date_of_birth=None,  # will set below
                phone=form['phone'],
                preferred_technique=form.get('technique'),
                tshirt_size=form['tshirtSize'],
                ski_experience=form.get('experience'),
                emergency_contact_name=form['emergencyName'],
                emergency_contact_relation=form['emergencyRelation'],
                emergency_contact_phone=form['emergencyPhone'],
                emergency_contact_email=form['emergencyEmail'],
            )
            phone_e164 = normalize_phone_e164(form['phone'])
            if identity is not None:
                # The verified number wins over whatever is typed in the form.
                phone_e164 = identity['phone_e164']
                user_fields['phone'] = format_phone_display(phone_e164)

            # Convert dob string to date object
            dob_str = form['dob']
            if dob_str:
                try:
                    user_fields['date_of_birth'] = datetime.strptime(dob_str, DATE_FORMAT).date()
                except ValueError as e:
                    flash_error('Invalid date format for Date of Birth. Please use YYYY-MM-DD.')
                    return redirect(url_for('registration.season_register', season_id=season_id))

            is_valid, validation_errors = validate_registration_form(
                form, user_fields.get('date_of_birth'))
            volunteer_interests, volunteer_committees, volunteer_errors = (
                validate_volunteer_selections(
                    form.getlist('volunteerInterests'),
                    form.getlist('volunteerCommittees')))
            validation_errors.extend(volunteer_errors)
            if not is_valid or volunteer_errors:
                for error in validation_errors:
                    flash_error(error)
                return redirect(url_for('registration.season_register', season_id=season_id))

            if user:
                for k, v in user_fields.items():
                    setattr(user, k, v)
                # Phone is the identity proof, so a resolved member may move
                # their email. The collision check above already rejected an
                # address belonging to a different account.
                user.email = email
            else:
                user = User(email=email, status=UserStatus.PENDING, **user_fields)
                db.session.add(user)
                db.session.flush()  # get user.id

            user.phone_e164 = phone_e164
            if identity is not None:
                user.phone_verified_at = user.phone_verified_at or datetime.utcnow()
            else:
                # No session identity means this phone_e164 is only the
                # typed form value — clear any stale verified-at from a
                # prior legitimate verification so a reused/updated row
                # never carries an unverified number that looks verified.
                user.phone_verified_at = None

            # Link payment to user if webhook created it before form submission
            if existing_payment and not existing_payment.user_id:
                existing_payment.user_id = user.id

            # Determine member_type from backend (already validated above,
            # gated the same way is_returning is: unverified stays 'new')
            member_type = member_type_str

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
                    status=UserSeasonStatus.ACTIVE if is_returning else UserSeasonStatus.PENDING_LOTTERY,
                    needs_review=needs_review,
                    review_note=review_note,
                    volunteer_interests=volunteer_interests,
                    volunteer_committees=volunteer_committees,
                )
                db.session.add(user_season)
            else:
                user_season.registration_type = member_type
                user_season.registration_date = current_time.date()
                user_season.status = UserSeasonStatus.ACTIVE if is_returning else UserSeasonStatus.PENDING_LOTTERY
                user_season.needs_review = needs_review
                user_season.review_note = review_note
                user_season.volunteer_interests = volunteer_interests
                user_season.volunteer_committees = volunteer_committees

            db.session.commit()
            payment_hold = not is_returning
            amount_display = f"${season.price_cents / 100:.2f}" if season.price_cents else None
            if is_returning:
                send_sms(user, 'confirmation_returning',
                         season_name=season.name, amount=amount_display)
            else:
                send_sms(user, 'confirmation_lottery', season_name=season.name)
            clear_verified_identity()
            return render_template('season_success.html',
                season=season,
                payment_hold=payment_hold,
                amount_display=amount_display,
                member_type=member_type
            )
        except Exception as e:
            flash_error(f'Error submitting registration: {str(e)}')
            return redirect(url_for('registration.season_register', season_id=season_id))

    # --- GET Request Handling ---
    if not season.is_any_registration_open(now_utc) and not invite_season_match:
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

    # If GET request and registration is open (or valid invite), render the form
    return render_template(
        'season_register.html',
        season=season,
        invite_token=invite_token if invite_season_match else None,
        invite_email=invite_payload.get('email') if invite_season_match else None,
    )

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
    result = {'is_returning': is_returning}
    if not is_returning:
        season = None
        season_id = data.get('season_id')
        if season_id is not None:
            try:
                season = Season.query.get(int(season_id))
            except (TypeError, ValueError):
                season = None
        result['new_registration_open'] = bool(season and season.is_new_open())
    return jsonify(result)
