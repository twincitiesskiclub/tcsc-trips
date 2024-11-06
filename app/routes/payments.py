from flask import Blueprint, jsonify, request
import json
import stripe
import os
from ..models import db, Payment

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

        # Save payment info to database
        payment = Payment(
            payment_intent_id=intent.id,
            email=email,
            name=name,
            amount=amount,
            trip_id=trip_id,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

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

        if event_type == 'payment_intent.succeeded':
            # Update payment status in database
            payment = Payment.query.filter_by(payment_intent_id=data_object.id).first()
            if payment:
                payment.status = 'completed'
                db.session.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'error': str(e)}), 400
