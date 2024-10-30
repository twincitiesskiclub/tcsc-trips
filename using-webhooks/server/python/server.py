#! /usr/bin/env python3.6
# server.py

import stripe
import json
import os

from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv, find_dotenv

# Setup Stripe python client library
load_dotenv(find_dotenv())
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION')

static_dir = str(os.path.abspath(os.path.join(__file__ , "..", os.getenv("STATIC_DIR"))))
app = Flask(__name__, static_folder=static_dir,
            static_url_path="", template_folder=static_dir)


@app.route('/', methods=['GET'])
def get_checkout_page():
    return render_template('index.html')


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
        
        # Get amount from the request data
        amount = float(data.get('amount', 135.00))
        
        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=calculate_order_amount(amount),
            currency=data['currency'],
            capture_method="manual"
        )

        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntent': {
                'id': intent.id,
                'amount': intent.amount,
                'status': intent.status
            }
        })
    except Exception as e:
        return jsonify(error=str(e)), 403


@app.route('/update-payment-intent', methods=['POST'])
def update_payment():
    try:
        data = json.loads(request.data)
        
        # Get payment intent ID and new amount from the request data
        payment_intent_id = data.get('paymentIntentId')
        amount = float(data.get('amount', 135.00))
        
        # Update the existing PaymentIntent
        intent = stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=calculate_order_amount(amount)
        )

        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntent': {
                'id': intent.id,
                'amount': intent.amount,
                'status': intent.status
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
        print('❗ Charging the card for: ' + str(data_object['amount_capturable']))
        intent = stripe.PaymentIntent.capture(data_object['id'])
    elif event_type == 'payment_intent.succeeded':
        print('💰 Payment received!')
    elif event_type == 'payment_intent.payment_failed':
        print('❌ Payment failed.')
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run()
