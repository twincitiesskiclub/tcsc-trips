from flask import Blueprint, jsonify, request
import json
import stripe
import os
from ..models import db, Payment, Season, UserSeason, User
from ..auth import admin_required
from ..constants import MemberType
from datetime import datetime

payments = Blueprint('payments', __name__)

@payments.route('/get-stripe-key')
def get_stripe_key():
    return jsonify({'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY')})

@payments.route('/create-payment-intent', methods=['POST'])
def create_payment():
    try:
        data = json.loads(request.data)
        email = data.get('email', '')
        name = data.get('name', '')
        amount = float(data.get('amount', 135.00))
        trip_id = request.referrer.split('/')[-1] if request.referrer else 'generic-trip'

        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='usd',
            capture_method='manual',
            receipt_email=email,
            metadata={
                'name': name,
                'email': email,
                'trip_id': trip_id
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
        return jsonify(error=str(e)), 403

@payments.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

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

        if event_type == 'payment_intent.amount_capturable_updated':
            # Create database entry only when payment is successfully authorized
            payment_intent = data_object
            member_type = payment_intent.metadata.get('member_type')
            season_id = payment_intent.metadata.get('season_id')
            email = payment_intent.metadata.get('email')
            name = payment_intent.metadata.get('name')
            # Only for NEW members
            if member_type == MemberType.NEW.value:
                # Find or create user
                user = User.query.filter_by(email=email).first()
                if not user:
                    # Split name if possible
                    first_name, last_name = (name.split(' ', 1) + [""])[:2]
                    user = User(email=email, first_name=first_name, last_name=last_name, status='pending')
                    db.session.add(user)
                    db.session.commit()
                # Check if UserSeason exists
                user_season = UserSeason.query.filter_by(user_id=user.id, season_id=season_id).first()
                if not user_season:
                    user_season = UserSeason(
                        user_id=user.id,
                        season_id=season_id,
                        registration_type=member_type,
                        registration_date=datetime.utcnow().date(),
                        status='pending_lottery'
                    )
                    db.session.add(user_season)
                    db.session.commit()
        elif event_type == 'payment_intent.succeeded':
            payment_intent = data_object
            member_type = payment_intent.metadata.get('member_type')
            season_id = payment_intent.metadata.get('season_id')
            email = payment_intent.metadata.get('email')
            # Find user
            user = User.query.filter_by(email=email).first()
            if user:
                user_season = UserSeason.query.filter_by(user_id=user.id, season_id=season_id).first()
                if user_season:
                    user_season.status = 'active'
                    user_season.payment_date = datetime.utcnow().date()
                    user.status = 'active'
                    db.session.commit()
        elif event_type == 'payment_intent.canceled':
            # Clean up any existing payment record if it exists
            payment = Payment.query.filter_by(payment_intent_id=data_object.id).first()
            if payment:
                db.session.delete(payment)
                db.session.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@payments.route('/admin/payments/<int:payment_id>/capture', methods=['POST'])
@admin_required
def capture_payment(payment_id):
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # First, retrieve the current payment intent status from Stripe
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)
        
        # Check if the payment is in a capturable state
        if intent.status != 'requires_capture':
            return jsonify({
                'error': f'Payment cannot be captured - current status: {intent.status}'
            }), 400

        # Attempt to capture the payment
        captured_intent = stripe.PaymentIntent.capture(payment.payment_intent_id)
        
        # Verify the capture was successful
        if captured_intent.status != 'succeeded':
            return jsonify({
                'error': f'Capture failed - status: {captured_intent.status}'
            }), 400

        # Update payment status in database
        payment.status = captured_intent.status
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'payment_intent_id': payment.payment_intent_id
            }
        })
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

@payments.route('/admin/payments/<int:payment_id>/refund', methods=['POST'])
@admin_required
def refund_payment(payment_id):
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # First, retrieve the current payment intent status from Stripe
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)
        
        # Check if the payment can be refunded
        if intent.status not in ['succeeded', 'requires_capture']:
            return jsonify({
                'error': f'Payment cannot be refunded - current status: {intent.status}'
            }), 400

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
                return jsonify({
                    'error': f'Refund failed - status: {refund.status}'
                }), 400
                
            payment.status = 'refunded'

        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'payment_intent_id': payment.payment_intent_id
            }
        })
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

@payments.route('/create-season-payment-intent', methods=['POST'])
def create_season_payment_intent():
    try:
        data = request.get_json()
        season_id = data.get('season_id')
        email = data.get('email', '').strip().lower()
        name = data.get('name', '')
        if not all([season_id, email, name]):
            return jsonify({'error': 'Missing required fields'}), 400
        season = Season.query.get(season_id)
        if not season or not season.price_cents:
            return jsonify({'error': 'Invalid season or price'}), 400
        # Derive member_type on the backend
        user = User.query.filter_by(email=email).one_or_none()
        member_type = 'returning' if user and user.is_returning else 'new'
        # Determine capture method
        if member_type == 'new':
            capture_method = 'manual'
        elif member_type == 'returning':
            capture_method = 'automatic'
        else:
            return jsonify({'error': 'Invalid member_type'}), 400
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            metadata={
                'name': name,
                'email': email,
                'season_id': str(season_id),
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
        return jsonify({'error': str(e)}), 403
