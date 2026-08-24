from flask import Blueprint, current_app, jsonify, request
import re
import stripe
import os
from datetime import datetime
from ..models import db, Payment, Season, UserSeason, User, Trip
from ..events.models import EventRegistration, RegistrationStatus
from ..auth import admin_required
from ..constants import MemberType, StripeEvent, UserStatus, UserSeasonStatus, PaymentType
from ..errors import json_error, json_success
from ..utils import normalize_email, today_central
from ..notifications.slack import send_payment_notification
from app.slack import trips as trip_slack
from ..security import csrf
from .. import late_link
from app.verify.service import get_verified_identity

payments = Blueprint('payments', __name__)


def _stripe_object_value(stripe_object, key, default=None):
    """Read a field from either Stripe's object or development webhook JSON."""
    if isinstance(stripe_object, dict):
        return stripe_object.get(key, default)
    return getattr(stripe_object, key, default)


def _season_email_fallback_user(email, payment_intent_id):
    """Resolve only a fresh webhook stub when an intent has no user_id."""
    candidate = User.get_by_email(email)
    if candidate is None:
        return None, False
    if (
        candidate.status == UserStatus.PENDING
        and not candidate.is_returning
    ):
        return candidate, False

    current_app.logger.warning(
        "PaymentIntent %s had no user_id; refusing email fallback to "
        "existing member %s",
        payment_intent_id,
        candidate.id,
    )
    return None, True


def _event_registration_from_metadata(metadata):
    registration_id = metadata.get('registration_id')
    try:
        registration_id = int(registration_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(EventRegistration, registration_id)


def _record_succeeded_event_payment(payment_intent):
    """Record and confirm an event payment without looking up a User."""
    metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
    payment_intent_id = _stripe_object_value(payment_intent, 'id')
    amount = _stripe_object_value(payment_intent, 'amount')
    email = normalize_email(metadata.get('email') or '')
    name = metadata.get('name') or ''
    registration = _event_registration_from_metadata(metadata)

    if registration is None:
        current_app.logger.warning(
            "Event registration %s was not found for PaymentIntent %s",
            metadata.get('registration_id'),
            payment_intent_id,
        )

    payment = Payment.get_by_payment_intent(payment_intent_id)
    if not payment:
        payment = Payment(
            payment_intent_id=payment_intent_id,
            email=email,
            name=name,
            amount=amount,
            status='succeeded',
            payment_type=PaymentType.EVENT,
            event_registration_id=(
                registration.id if registration is not None else None
            ),
            user_id=None,
        )
        db.session.add(payment)
    else:
        payment.status = 'succeeded'
        if registration is not None and not payment.event_registration_id:
            payment.event_registration_id = registration.id

    if registration is not None:
        registration.status = RegistrationStatus.CONFIRMED

    db.session.commit()
    send_payment_notification(
        name=payment.name,
        amount_cents=payment.amount,
        email=payment.email,
        payment_intent_id=payment.payment_intent_id,
    )


def _cancel_event_registration(payment_intent):
    """Cancel a pending event registration for a canceled intent."""
    metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
    registration = _event_registration_from_metadata(metadata)
    if (
        registration is not None
        and registration.status == RegistrationStatus.PENDING_PAYMENT
    ):
        registration.status = RegistrationStatus.CANCELLED

    payment_intent_id = _stripe_object_value(payment_intent, 'id')
    payment = Payment.get_by_payment_intent(payment_intent_id)
    if payment:
        payment.status = 'canceled'

    db.session.commit()


def _trip_registration_from_metadata(metadata):
    from app.trips.models import TripRegistration
    registration_id = metadata.get('registration_id')
    payment_type = metadata.get('payment_type')
    if payment_type != PaymentType.TRIP or not registration_id:
        return None
    try:
        return db.session.get(TripRegistration, int(registration_id))
    except (TypeError, ValueError):
        return None


def _transition_trip_registration(payment_intent, new_status):
    """Legacy trip intents without registration_id are silently skipped; repeats of the same status are no-ops (no re-DM)."""
    from app.trips.models import TripRegistrationStatus
    metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
    registration = _trip_registration_from_metadata(metadata)
    if registration is None:
        return
    if registration.status == new_status:
        return  # idempotent webhook redelivery - no re-DM
    if (new_status == TripRegistrationStatus.CANCELLED
            and registration.status == TripRegistrationStatus.CONFIRMED):
        return
    registration.status = new_status
    db.session.commit()
    if new_status == TripRegistrationStatus.PENDING:
        trip_slack.send_registration_dm(registration)
    elif new_status == TripRegistrationStatus.CONFIRMED:
        trip_slack.send_confirmation_dm(registration)
        trip_slack.invite_to_trip_channel(registration)


def build_statement_descriptor(payment_type, identifier):
    prefix = f"TCSC_{payment_type}_"
    sanitized = re.sub(r'[^A-Z0-9_ .\-]', '', identifier.upper())
    return (prefix + sanitized)[:22]


def stripe_idempotency_options():
    """Forward the browser's per-attempt key using Stripe's request option."""
    idempotency_key = request.headers.get('Idempotency-Key')
    if not idempotency_key:
        return {}
    return {'idempotency_key': idempotency_key[:255]}


def _log_unknown_payment_type(payment_type, payment_intent_id):
    if payment_type not in PaymentType.ALL:
        current_app.logger.warning(
            "Recording PaymentIntent %s with unknown payment_type %r",
            payment_intent_id,
            payment_type,
        )


def refund_or_cancel_payment(payment):
    """Refund a captured payment or cancel an uncaptured payment.

    The caller owns any related model updates and the database commit.
    """
    intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)
    if intent.status not in ['succeeded', 'requires_capture']:
        raise ValueError(
            'Payment cannot be refunded - '
            f'current status: {intent.status}'
        )

    if intent.status == 'requires_capture':
        canceled_intent = stripe.PaymentIntent.cancel(
            payment.payment_intent_id
        )
        payment.status = canceled_intent.status
    else:
        refund = stripe.Refund.create(
            payment_intent=payment.payment_intent_id
        )
        if refund.status not in ('succeeded', 'pending'):
            raise ValueError(f'Refund failed - status: {refund.status}')
        payment.status = 'refunded'

    return payment


@payments.route('/get-stripe-key')
def get_stripe_key():
    return jsonify({'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY')})

@payments.route('/create-payment-intent', methods=['POST'])
def create_payment():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get('email', ''))
        name = (data.get('name') or '').strip()
        trip_slug = (data.get('trip_slug') or '').strip()
        price_tier = data.get('price_tier')

        if not all([email, name, trip_slug, price_tier]):
            return json_error('Missing required fields')

        # Price and trip identity must come from the database, never from the
        # browser-provided amount or Referer header.
        trip = Trip.query.filter_by(slug=trip_slug).first()
        if not trip:
            return json_error('Trip not found')
        if trip.status != 'active' or not (trip.signup_start <= datetime.utcnow() <= trip.signup_end):
            return json_error('Trip registration is not currently open')
        if price_tier == 'low':
            amount_cents = trip.price_low
        elif price_tier == 'high':
            amount_cents = trip.price_high
        else:
            return json_error('Invalid trip price option')

        # Determine member type based on whether user exists and has active seasons
        user = User.get_by_email(email)
        member_type = MemberType.RETURNING.value if user and user.is_returning else MemberType.NEW.value

        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=email,
            statement_descriptor=build_statement_descriptor('TRIP', trip.name),
            description=f"TCSC Trip - {trip.name}",
            metadata={
                'name': name,
                'email': email,
                'payment_type': PaymentType.TRIP,
                'trip_id': str(trip.id),
                'trip_slug': trip_slug,
                'price_tier': price_tier,
                'member_type': member_type
            },
            **stripe_idempotency_options(),
        )

        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntent': {
                'id': intent.id,
                'amount': intent.amount,
                'status': intent.status,
                'email': email
            }
        })
    except Exception as e:
        return json_error(str(e), 500)

@payments.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = request.get_json()

    try:
        if webhook_secret:
            signature = request.headers.get('stripe-signature')
            event = stripe.Webhook.construct_event(
                payload=request.data,
                sig_header=signature,
                secret=webhook_secret
            )
            data = event['data']
        elif os.getenv('FLASK_ENV') == 'development':
            data = request_data['data']
            event = request_data
        else:
            return json_error('Webhook signature verification not configured', 500)

        # Get the type of webhook event sent
        event_type = event['type']
        data_object = data['object']

        if event_type == StripeEvent.PAYMENT_CAPTURABLE:
            # Payment authorized but not yet captured (new members with manual capture)
            payment_intent = data_object
            metadata = (
                _stripe_object_value(payment_intent, 'metadata', {}) or {}
            )
            payment_intent_id = _stripe_object_value(payment_intent, 'id')
            amount = _stripe_object_value(payment_intent, 'amount')
            payment_type = metadata.get(
                'payment_type',
                PaymentType.SEASON,
            )
            member_type = (
                metadata.get('member_type') or ''
            ).upper()
            season_id = metadata.get('season_id')
            trip_id = metadata.get('trip_id')
            email = normalize_email(metadata.get('email') or '')
            name = metadata.get('name') or ''
            _log_unknown_payment_type(payment_type, payment_intent_id)

            # Season intents carry the verified account id. Resolve it before
            # email so an address change cannot create a duplicate stub. Trips
            # do not emit user_id and keep their existing email-only behavior.
            user = None
            metadata_user_id = ''
            blocked_email_fallback = False
            if payment_type == PaymentType.SEASON:
                metadata_user_id = metadata.get('user_id') or ''
                if metadata_user_id.isdigit():
                    user = User.query.get(int(metadata_user_id))

                if metadata_user_id and user is None:
                    current_app.logger.warning(
                        "PaymentIntent %s carried unresolved user_id %s",
                        payment_intent_id,
                        metadata_user_id,
                    )
                elif user is None:
                    user, blocked_email_fallback = (
                        _season_email_fallback_user(
                            email, payment_intent_id)
                    )
            else:
                user = User.get_by_email(email)

            # Create new user only if not found and member_type is NEW
            if (
                not user
                and not metadata_user_id
                and not blocked_email_fallback
                and member_type == MemberType.NEW.value
            ):
                first_name, last_name = (name.split(' ', 1) + [""])[:2]
                user = User(email=email, first_name=first_name, last_name=last_name, status=UserStatus.PENDING)
                db.session.add(user)
                db.session.commit()

            # Create UserSeason for season payments (for any user, found or created)
            if user and payment_type == PaymentType.SEASON and season_id:
                user_season = UserSeason.get_for_user_season(user.id, season_id)
                if not user_season:
                    user_season = UserSeason(
                        user_id=user.id,
                        season_id=season_id,
                        registration_type=member_type,
                        registration_date=today_central(),
                        status=UserSeasonStatus.PENDING_LOTTERY
                    )
                    db.session.add(user_season)
                    db.session.commit()

            # Create Payment record (idempotent - check if exists first)
            payment = Payment.get_by_payment_intent(payment_intent_id)
            if not payment:
                payment = Payment(
                    payment_intent_id=payment_intent_id,
                    email=email,
                    name=name,
                    amount=amount,
                    status='requires_capture',
                    payment_type=payment_type,
                    season_id=int(season_id) if season_id else None,
                    trip_id=int(trip_id) if trip_id else None,
                    user_id=user.id if user else None
                )
                db.session.add(payment)
                db.session.commit()

            if payment_type == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    payment_intent, TripRegistrationStatus.PENDING)

        elif event_type == StripeEvent.PAYMENT_SUCCEEDED:
            # Payment captured (returning members auto-capture, or manual capture completed)
            payment_intent = data_object
            metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
            payment_type = metadata.get('payment_type', PaymentType.SEASON)
            if payment_type == PaymentType.EVENT:
                _record_succeeded_event_payment(payment_intent)
                return json_success()

            payment_intent_id = _stripe_object_value(payment_intent, 'id')
            amount = _stripe_object_value(payment_intent, 'amount')
            member_type = (metadata.get('member_type') or '').upper()
            season_id = metadata.get('season_id')
            trip_id = metadata.get('trip_id')
            email = normalize_email(metadata.get('email') or '')
            name = metadata.get('name') or ''
            _log_unknown_payment_type(payment_type, payment_intent_id)

            # Season intents carry the verified account id. Matching on email
            # alone creates a duplicate ACTIVE stub whenever a verified member
            # registers under a new address, which this change makes more
            # common, not less. Trips do not emit user_id and are left alone.
            user = None
            metadata_user_id = ''
            blocked_email_fallback = False
            if payment_type == PaymentType.SEASON:
                metadata_user_id = metadata.get('user_id') or ''
                if metadata_user_id.isdigit():
                    user = User.query.get(int(metadata_user_id))

                if metadata_user_id and user is None:
                    current_app.logger.warning(
                        "PaymentIntent %s carried unresolved user_id %s",
                        payment_intent_id,
                        metadata_user_id,
                    )
                elif user is None:
                    user, blocked_email_fallback = (
                        _season_email_fallback_user(
                            email, payment_intent_id)
                    )
            else:
                user = User.get_by_email(email)
            if (
                not user
                and not metadata_user_id
                and not blocked_email_fallback
                and member_type == MemberType.RETURNING.value
            ):
                # Returning member should already exist, but create if not
                first_name, last_name = (name.split(' ', 1) + [""])[:2]
                user = User(email=email, first_name=first_name, last_name=last_name, status=UserStatus.ACTIVE)
                db.session.add(user)
                db.session.commit()

            # Update UserSeason for season payments
            if payment_type == PaymentType.SEASON and season_id and user:
                user_season = UserSeason.get_for_user_season(user.id, season_id)
                if user_season:
                    user_season.status = UserSeasonStatus.ACTIVE
                    user_season.payment_date = today_central()
                    user.sync_status()
                elif member_type == MemberType.RETURNING.value:
                    # Create UserSeason for returning member
                    user_season = UserSeason(
                        user_id=user.id,
                        season_id=season_id,
                        registration_type=member_type,
                        registration_date=today_central(),
                        payment_date=today_central(),
                        status=UserSeasonStatus.ACTIVE
                    )
                    db.session.add(user_season)
                    user.sync_status()

            # Create or update Payment record
            payment = Payment.get_by_payment_intent(payment_intent_id)
            if not payment:
                payment = Payment(
                    payment_intent_id=payment_intent_id,
                    email=email,
                    name=name,
                    amount=amount,
                    status='succeeded',
                    payment_type=payment_type,
                    season_id=int(season_id) if season_id else None,
                    trip_id=int(trip_id) if trip_id else None,
                    user_id=user.id if user else None
                )
                db.session.add(payment)
            else:
                payment.status = 'succeeded'
                if user and not payment.user_id:
                    payment.user_id = user.id

            db.session.commit()

            # Send Slack notification for successful payment
            send_payment_notification(
                name=payment.name,
                amount_cents=payment.amount,
                email=payment.email,
                payment_intent_id=payment.payment_intent_id
            )

            if payment_type == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    payment_intent, TripRegistrationStatus.CONFIRMED)

        elif event_type == StripeEvent.PAYMENT_CANCELED:
            metadata = _stripe_object_value(data_object, 'metadata', {}) or {}
            if metadata.get('payment_type') == PaymentType.EVENT:
                _cancel_event_registration(data_object)
                return json_success()

            payment_intent_id = _stripe_object_value(data_object, 'id')
            payment = Payment.get_by_payment_intent(payment_intent_id)
            if payment:
                payment.status = 'canceled'
                if payment.payment_type == PaymentType.SEASON and payment.season_id:
                    user = User.get_by_email(payment.email)
                    if user:
                        user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                        if user_season:
                            user_season.status = UserSeasonStatus.DROPPED_VOLUNTARY
                            user.sync_status()
                db.session.commit()

            if metadata.get('payment_type') == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    data_object, TripRegistrationStatus.CANCELLED)

        return json_success()

    except Exception as e:
        return json_error('Webhook processing failed', 500)

@payments.route('/admin/payments/<int:payment_id>/capture', methods=['POST'])
@admin_required
def capture_payment(payment_id):
    try:
        payment = Payment.query.get_or_404(payment_id)

        # First, retrieve the current payment intent status from Stripe
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)

        # Check if the payment is in a capturable state
        if intent.status != 'requires_capture':
            return json_error(f'Payment cannot be captured - current status: {intent.status}')

        # Attempt to capture the payment
        captured_intent = stripe.PaymentIntent.capture(payment.payment_intent_id)

        # Verify the capture was successful
        if captured_intent.status != 'succeeded':
            return json_error(f'Capture failed - status: {captured_intent.status}')

        # Update payment status in database
        payment.status = captured_intent.status

        # Auto-sync: Update UserSeason status for season payments
        if payment.payment_type == PaymentType.SEASON and payment.season_id:
            user = User.get_by_email(payment.email)
            if user:
                user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                if user_season:
                    user_season.status = UserSeasonStatus.ACTIVE
                    user_season.payment_date = today_central()
                    user.sync_status()
                # Link payment to user if not already linked
                if not payment.user_id:
                    payment.user_id = user.id

        db.session.commit()

        # Slack notification will be sent by the webhook handler
        # when Stripe fires payment_intent.succeeded event

        return json_success({
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'payment_intent_id': payment.payment_intent_id
            }
        })
    except stripe.error.StripeError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error('An unexpected error occurred', 500)

@payments.route('/admin/payments/<int:payment_id>/refund', methods=['POST'])
@admin_required
def refund_payment(payment_id):
    try:
        payment = Payment.query.get_or_404(payment_id)
        refund_or_cancel_payment(payment)

        # Auto-sync: Update UserSeason status for season payments
        if payment.payment_type == PaymentType.SEASON and payment.season_id:
            user = User.get_by_email(payment.email)
            if user:
                user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                if user_season:
                    user_season.status = UserSeasonStatus.DROPPED_VOLUNTARY
                    user.sync_status()

        db.session.commit()

        return json_success({
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'payment_intent_id': payment.payment_intent_id
            }
        })
    except ValueError as e:
        return json_error(str(e))
    except stripe.error.StripeError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error('An unexpected error occurred', 500)

@payments.route('/admin/payments/bulk-capture', methods=['POST'])
@admin_required
def bulk_capture_payments():
    """Capture multiple payments at once."""
    try:
        data = request.get_json()
        payment_ids = data.get('payment_ids', [])

        if not payment_ids:
            return json_error('No payment IDs provided')

        results = []
        for payment_id in payment_ids:
            try:
                payment = Payment.query.get(payment_id)
                if not payment:
                    results.append({'id': payment_id, 'success': False, 'error': 'Payment not found'})
                    continue

                # Retrieve current status from Stripe
                intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)

                if intent.status != 'requires_capture':
                    results.append({'id': payment_id, 'success': False, 'error': f'Cannot capture - status: {intent.status}'})
                    continue

                # Capture the payment
                captured_intent = stripe.PaymentIntent.capture(payment.payment_intent_id)

                if captured_intent.status != 'succeeded':
                    results.append({'id': payment_id, 'success': False, 'error': f'Capture failed - status: {captured_intent.status}'})
                    continue

                # Update payment status
                payment.status = captured_intent.status

                # Auto-sync: Update UserSeason status for season payments
                if payment.payment_type == PaymentType.SEASON and payment.season_id:
                    user = User.get_by_email(payment.email)
                    if user:
                        user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                        if user_season:
                            user_season.status = UserSeasonStatus.ACTIVE
                            user_season.payment_date = today_central()
                            user.sync_status()
                        if not payment.user_id:
                            payment.user_id = user.id

                results.append({'id': payment_id, 'success': True})

            except stripe.error.StripeError as e:
                results.append({'id': payment_id, 'success': False, 'error': str(e)})
            except Exception as e:
                results.append({'id': payment_id, 'success': False, 'error': str(e)})

        db.session.commit()

        return json_success({'results': results})

    except Exception as e:
        return json_error(str(e), 500)


@payments.route('/admin/payments/bulk-refund', methods=['POST'])
@admin_required
def bulk_refund_payments():
    """Refund or cancel multiple payments at once."""
    try:
        data = request.get_json()
        payment_ids = data.get('payment_ids', [])

        if not payment_ids:
            return json_error('No payment IDs provided')

        results = []
        for payment_id in payment_ids:
            try:
                payment = Payment.query.get(payment_id)
                if not payment:
                    results.append({'id': payment_id, 'success': False, 'error': 'Payment not found'})
                    continue

                refund_or_cancel_payment(payment)

                # Auto-sync: Update UserSeason status for season payments
                if payment.payment_type == PaymentType.SEASON and payment.season_id:
                    user = User.get_by_email(payment.email)
                    if user:
                        user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                        if user_season:
                            user_season.status = UserSeasonStatus.DROPPED_VOLUNTARY
                            user.sync_status()

                results.append({'id': payment_id, 'success': True})

            except ValueError as e:
                results.append({'id': payment_id, 'success': False, 'error': str(e)})
            except stripe.error.StripeError as e:
                results.append({'id': payment_id, 'success': False, 'error': str(e)})
            except Exception as e:
                results.append({'id': payment_id, 'success': False, 'error': str(e)})

        db.session.commit()

        return json_success({'results': results})

    except Exception as e:
        return json_error(str(e), 500)


@payments.route('/create-season-payment-intent', methods=['POST'])
def create_season_payment_intent():
    try:
        data = request.get_json()
        season_id = data.get('season_id')
        email = normalize_email(data.get('email', ''))
        name = data.get('name', '')
        invite_token = data.get('invite')
        if not all([season_id, email, name]):
            return json_error('Missing required fields')
        season = Season.query.get(season_id)
        if not season or not season.price_cents:
            return json_error('Invalid season or price')
        # Identity comes from the verified session, never the typed email.
        identity = get_verified_identity()
        verified_user = None
        if identity and identity.get('user_id'):
            verified_user = User.query.get(identity['user_id'])
        if (
            verified_user is not None
            and email != normalize_email(verified_user.email)
            and User.get_by_email(email) is not None
        ):
            return json_error(
                'That email belongs to another member. Use a different one.'
            )
        # A verified phone that resolved to one account IS that member, so
        # changing to an unclaimed email is a profile edit, not grounds to
        # demote them to a hold.
        #
        # This is only safe because POST /api/verify/disclaim nulls user_id
        # server-side when someone clicks "Not [name]?". This endpoint gets
        # no disclaim signal of its own, so that call is what stands between
        # a household member and an automatic full charge on a returning
        # member's classification. Do not remove one without the other.
        if verified_user is not None and verified_user.is_returning:
            member_type = MemberType.RETURNING.value
        else:
            member_type = MemberType.NEW.value
        verified = identity is not None and verified_user is not None
        # A valid invite token for this (season, email) bypasses the window gate.
        invite_payload = late_link.verify(invite_token) if invite_token else None
        invite_valid_for_email = (
            invite_payload is not None
            and invite_payload.get('season_id') == int(season_id)
            and invite_payload.get('email') == email
        )
        # Reject if the registration window for this member_type is closed.
        # Prevents stub User rows from being created via the webhook when the
        # form POST would have rejected the registration anyway.
        if not invite_valid_for_email and not season.is_open_for(member_type.lower(), datetime.utcnow()):
            return json_error(
                f"Registration for {member_type.lower()} members is not currently open."
            )
        existing_payment = Payment.query.filter(
            Payment.email == email,
            Payment.season_id == int(season_id),
            Payment.status.notin_(['canceled', 'refunded'])
        ).first()
        if existing_payment:
            return json_error('You have already registered for this season.')
        # Returning members are guaranteed a spot: charge immediately.
        # Everyone else (new or unverified) gets a hold; see CLAUDE.md.
        capture_method = 'automatic' if member_type == MemberType.RETURNING.value else 'manual'
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            statement_descriptor=build_statement_descriptor('SEASON', str(season.year)),
            description=f"TCSC {season.name} Membership",
            metadata={
                'name': name,
                'email': email,
                'season_id': str(season_id),
                'member_type': member_type,
                'payment_type': PaymentType.SEASON,
                'verified': 'true' if verified else 'false',
                # The webhook matches on email today, so a member typing a
                # new address can get a duplicate stub User. This change
                # makes email edits more common, so carry the id.
                'user_id': str(verified_user.id) if verified_user else '',
            },
            **stripe_idempotency_options(),
        )
        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntent': {
                'id': intent.id,
                'amount': intent.amount,
                'status': intent.status,
                'email': email
            }
        })
    except Exception as e:
        return json_error(str(e), 500)
