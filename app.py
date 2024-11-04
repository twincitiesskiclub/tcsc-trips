#! /usr/bin/env python3.6
# app.py

import stripe
import json
import os
from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv, find_dotenv

# Setup Stripe python client library
load_dotenv(find_dotenv())
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION')

# Initialize Flask app with standard directory structure
app = Flask(__name__,
           static_folder='static',
           static_url_path='/static')

@app.route('/', methods=['GET'])
def get_home_page():
    return render_template('index.html')


@app.route('/training-trip', methods=['GET'])
def get_training_trip_page():
    return render_template('training-trip.html')


@app.route('/get-stripe-key', methods=['GET'])
def get_stripe_key():
    return jsonify({
        'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY')
    })


def calculate_order_amount(amount):
    # Convert decimal amount to cents (e.g., 135.00 -> 13500)
    amount_in_cents = int(amount * 100)
    
    # Validate the amount is one of our accepted prices
    accepted_amounts = [13500, 16000]  # $135.00 or $160.00 in cents
    
    if amount_in_cents not in accepted_amounts:
        # If amount is not valid, default to lower price
        return 13500
    
    return amount_in_cents


@app.route('/create-payment-intent', methods=['POST'])
def create_payment():
    try:
        data = json.loads(request.data)
        
        # Get amount and email from the request data
        amount = float(data.get('amount', 135.00))
        email = data.get('email', '')
        name = data.get('name', '')
        
        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=calculate_order_amount(amount),
            currency=data['currency'],
            capture_method="manual",
            metadata={
                'email': email,
                'name': name,
                'amount': str(amount)
            },
            receipt_email=email
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


@app.route('/update-payment-intent', methods=['POST'])
def update_payment():
    try:
        data = json.loads(request.data)
        
        # Get payment intent ID, new amount, and email from the request data
        payment_intent_id = data.get('paymentIntentId')
        amount = float(data.get('amount', 135.00))
        email = data.get('email', '')
        
        # Update the existing PaymentIntent
        intent = stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=calculate_order_amount(amount),
            metadata={
                'email': email,
                'amount': str(amount)
            },
            receipt_email=email
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


@app.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    if event_type == 'payment_intent.amount_capturable_updated':
        print('💳 Charging the card for: ' + str(data_object['amount_capturable']))
        # Get the email from metadata
        email = data_object.get('metadata', {}).get('email', '')
        print('📧 Customer email: ' + email)
        intent = stripe.PaymentIntent.capture(data_object['id'])
    elif event_type == 'payment_intent.succeeded':
        print('✅ Payment received!')
        # Get the email from metadata
        email = data_object.get('metadata', {}).get('email', '')
        print('📧 Payment confirmation sent to: ' + email)
    elif event_type == 'payment_intent.payment_failed':
        print('❌ Payment failed.')
        # Get the email from metadata for failure notification
        email = data_object.get('metadata', {}).get('email', '')
        print('📧 Payment failure notification for: ' + email)
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(port=os.getenv('PORT', 5000))
