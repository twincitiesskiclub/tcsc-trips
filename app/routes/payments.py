from flask import Blueprint, jsonify, request
import stripe
import os
from ..models import db, Payment, Season, UserSeason, User, Trip, SocialEvent
from ..auth import admin_required
from ..constants import MemberType, StripeEvent, UserStatus, UserSeasonStatus, PaymentType
from ..errors import json_error, json_success
from ..utils import normalize_email, today_central
from ..notifications.slack import send_payment_notification

payments = Blueprint('payments', __name__)

@payments.route('/get-stripe-key')
def get_stripe_key():
    return jsonify({'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY')})

@payments.route('/get-google-places-key')
def get_google_places_key():
    return jsonify({'apiKey': os.getenv('GOOGLE_PLACES_API_KEY', '')})

@payments.route('/create-payment-intent', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        email = normalize_email(data.get('email', ''))
        name = data.get('name', '')
        amount = float(data.get('amount', 135.00))
        trip_slug = request.referrer.split('/')[-1] if request.referrer else None

        # Look up trip by slug to get the actual trip_id
        trip = Trip.query.filter_by(slug=trip_slug).first() if trip_slug else None

        # Determine member type based on whether user exists and has active seasons
        user = User.get_by_email(email)
        member_type = MemberType.RETURNING.value if user and user.is_returning else MemberType.NEW.value

        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=email,
            metadata={
                'name': name,
                'email': email,
                'payment_type': PaymentType.TRIP,
                'trip_id': str(trip.id) if trip else None,
                'trip_slug': trip_slug,
                'member_type': member_type
            }
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
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = request.get_json()

    try:
        if webhook_secret:
            # Verify webhook signature and extract the event
            signature = request.headers.get('stripe-signature')
            event = stripe.Webhook.construct_event(
                payload=request.data,
                sig_header=signature,
                secret=webhook_secret
            )
            data = event['data']
        else:
            data = request_data['data']
            event = request_data

        # Get the type of webhook event sent
        event_type = event['type']
        data_object = data['object']

        if event_type == StripeEvent.PAYMENT_CAPTURABLE:
            # Payment authorized but not yet captured (new members with manual capture)
            payment_intent = data_object
            payment_type = payment_intent.metadata.get('payment_type', PaymentType.SEASON)
            member_type = (payment_intent.metadata.get('member_type') or '').upper()  # Normalize case
            season_id = payment_intent.metadata.get('season_id')
            trip_id = payment_intent.metadata.get('trip_id')
            social_event_id = payment_intent.metadata.get('social_event_id')
            email = normalize_email(payment_intent.metadata.get('email') or '')
            name = payment_intent.metadata.get('name') or ''

            # Always try to find existing user by email
            user = User.get_by_email(email)

            # Create new user only if not found and member_type is NEW
            if not user and member_type == MemberType.NEW.value:
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
            payment = Payment.get_by_payment_intent(payment_intent.id)
            if not payment:
                payment = Payment(
                    payment_intent_id=payment_intent.id,
                    email=email,
                    name=name,
                    amount=payment_intent.amount,
                    status='requires_capture',
                    payment_type=payment_type,
                    season_id=int(season_id) if season_id else None,
                    trip_id=int(trip_id) if trip_id else None,
                    social_event_id=int(social_event_id) if social_event_id else None,
                    user_id=user.id if user else None
                )
                db.session.add(payment)
                db.session.commit()

        elif event_type == StripeEvent.PAYMENT_SUCCEEDED:
            # Payment captured (returning members auto-capture, or manual capture completed)
            payment_intent = data_object
            payment_type = payment_intent.metadata.get('payment_type', PaymentType.SEASON)
            member_type = (payment_intent.metadata.get('member_type') or '').upper()  # Normalize case
            season_id = payment_intent.metadata.get('season_id')
            trip_id = payment_intent.metadata.get('trip_id')
            social_event_id = payment_intent.metadata.get('social_event_id')
            email = normalize_email(payment_intent.metadata.get('email') or '')
            name = payment_intent.metadata.get('name') or ''

            # Find or create user
            user = User.get_by_email(email)
            if not user and member_type == MemberType.RETURNING.value:
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
                    user.status = UserStatus.ACTIVE
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
                    user.status = UserStatus.ACTIVE

            # Create or update Payment record
            payment = Payment.get_by_payment_intent(payment_intent.id)
            if not payment:
                payment = Payment(
                    payment_intent_id=payment_intent.id,
                    email=email,
                    name=name,
                    amount=payment_intent.amount,
                    status='succeeded',
                    payment_type=payment_type,
                    season_id=int(season_id) if season_id else None,
                    trip_id=int(trip_id) if trip_id else None,
                    social_event_id=int(social_event_id) if social_event_id else None,
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

        elif event_type == StripeEvent.PAYMENT_CANCELED:
            # Payment was canceled - update status (don't delete, keep for audit)
            payment = Payment.get_by_payment_intent(data_object.id)
            if payment:
                payment.status = 'canceled'
                db.session.commit()

        return json_success()

    except Exception as e:
        return json_error(str(e))

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
                    user.status = UserStatus.ACTIVE
                # Link payment to user if not already linked
                if not payment.user_id:
                    payment.user_id = user.id

        db.session.commit()

        # Send Slack notification for successful capture
        send_payment_notification(
            name=payment.name,
            amount_cents=payment.amount,
            email=payment.email,
            payment_intent_id=payment.payment_intent_id
        )

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

        # First, retrieve the current payment intent status from Stripe
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)

        # Check if the payment can be refunded
        if intent.status not in ['succeeded', 'requires_capture']:
            return json_error(f'Payment cannot be refunded - current status: {intent.status}')

        # If payment is still on hold (requires_capture), we need to cancel it instead of refunding
        if intent.status == 'requires_capture':
            canceled_intent = stripe.PaymentIntent.cancel(payment.payment_intent_id)
            payment.status = canceled_intent.status
        else:
            # Create refund for captured payments
            refund = stripe.Refund.create(
                payment_intent=payment.payment_intent_id
            )

            # Verify the refund was successful
            if refund.status != 'succeeded':
                return json_error(f'Refund failed - status: {refund.status}')

            payment.status = 'refunded'

        # Auto-sync: Update UserSeason status for season payments
        if payment.payment_type == PaymentType.SEASON and payment.season_id:
            user = User.get_by_email(payment.email)
            if user:
                user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                if user_season:
                    user_season.status = UserSeasonStatus.DROPPED

        db.session.commit()

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
                            user.status = UserStatus.ACTIVE
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

                # Retrieve current status from Stripe
                intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)

                if intent.status not in ['succeeded', 'requires_capture']:
                    results.append({'id': payment_id, 'success': False, 'error': f'Cannot refund - status: {intent.status}'})
                    continue

                # Cancel uncaptured payments, refund captured ones
                if intent.status == 'requires_capture':
                    canceled_intent = stripe.PaymentIntent.cancel(payment.payment_intent_id)
                    payment.status = canceled_intent.status
                else:
                    refund = stripe.Refund.create(payment_intent=payment.payment_intent_id)
                    if refund.status != 'succeeded':
                        results.append({'id': payment_id, 'success': False, 'error': f'Refund failed - status: {refund.status}'})
                        continue
                    payment.status = 'refunded'

                # Auto-sync: Update UserSeason status for season payments
                if payment.payment_type == PaymentType.SEASON and payment.season_id:
                    user = User.get_by_email(payment.email)
                    if user:
                        user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                        if user_season:
                            user_season.status = UserSeasonStatus.DROPPED

                results.append({'id': payment_id, 'success': True})

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
        if not all([season_id, email, name]):
            return json_error('Missing required fields')
        season = Season.query.get(season_id)
        if not season or not season.price_cents:
            return json_error('Invalid season or price')
        # Derive member_type on the backend
        user = User.get_by_email(email)
        member_type = MemberType.RETURNING.value if user and user.is_returning else MemberType.NEW.value
        # Determine capture method
        if member_type == MemberType.NEW.value:
            capture_method = 'manual'
        elif member_type == MemberType.RETURNING.value:
            capture_method = 'automatic'
        else:
            return json_error('Invalid member_type')
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            metadata={
                'name': name,
                'email': email,
                'season_id': str(season_id),
                'member_type': member_type,
                'payment_type': PaymentType.SEASON
            }
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


@payments.route('/create-social-event-payment-intent', methods=['POST'])
def create_social_event_payment_intent():
    """Create a payment intent for social event registration.

    Social events use automatic capture (immediate charge) - no lottery system.
    """
    try:
        data = request.get_json()
        social_event_id = data.get('social_event_id')
        email = normalize_email(data.get('email', ''))
        name = data.get('name', '')

        if not all([social_event_id, email, name]):
            return json_error('Missing required fields')

        social_event = SocialEvent.query.get(social_event_id)
        if not social_event:
            return json_error('Social event not found')

        # Create PaymentIntent with AUTOMATIC capture (immediate charge)
        intent = stripe.PaymentIntent.create(
            amount=social_event.price,
            currency='usd',
            capture_method='automatic',  # Immediate charge - no lottery
            receipt_email=email,
            metadata={
                'name': name,
                'email': email,
                'payment_type': PaymentType.SOCIAL_EVENT,
                'social_event_id': str(social_event.id),
                'social_event_slug': social_event.slug
            }
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
