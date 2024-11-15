from flask import Blueprint, jsonify, request
import json
import stripe
import os
from ..models import db, Payment
from ..auth import admin_required

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

        if event_type == 'payment_intent.requires_capture':
            # Create database entry only when payment is successfully authorized
            payment_intent = data_object
            payment = Payment(
                payment_intent_id=payment_intent.id,
                email=payment_intent.metadata.get('email'),
                name=payment_intent.metadata.get('name'),
                amount=payment_intent.amount / 100,  # Convert from cents
                trip_id=payment_intent.metadata.get('trip_id'),
                status='requires_capture'
            )
            db.session.add(payment)
            db.session.commit()
        elif event_type == 'payment_intent.succeeded':
            # Update payment status in database
            payment = Payment.query.filter_by(payment_intent_id=data_object.id).first()
            if payment:
                payment.status = 'completed'
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
