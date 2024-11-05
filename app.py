#! /usr/bin/env python3.6
# app.py

import stripe
import json
import os
from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv, find_dotenv
from flask_sqlalchemy import SQLAlchemy
from models import db, Payment

# Setup Stripe python client library
load_dotenv(find_dotenv())
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION')

# Initialize Flask app with standard directory structure
app = Flask(__name__,
           static_folder='static',
           static_url_path='/static')

# Add these configurations after creating the Flask app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///payments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Load environment variables from .env file
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

# Get environment setting
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')

# Database configuration
if ENVIRONMENT == 'production':
    db_path = '/var/lib/payments.db'
elif ENVIRONMENT == 'development':
    db_path = os.path.join(basedir, 'instance', 'payments.db')
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
elif ENVIRONMENT == 'testing':
    db_path = os.path.join(basedir, 'instance', 'test.db')
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
else:
    raise ValueError(f"Invalid FLASK_ENV value: {ENVIRONMENT}")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

# Initialize the database
db.init_app(app)

# Create tables (add this after db initialization)
with app.app_context():
    db.create_all()

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
        amount = float(data.get('amount', 135.00))
        email = data.get('email', '')
        name = data.get('name', '')
        
        # Get trip_id from referrer or default to 'generic-trip'
        trip_id = request.referrer.split('/')[-1] if request.referrer else 'generic-trip'
        
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=calculate_order_amount(amount),
            currency=data['currency'],
            capture_method="manual",
            metadata={
                'email': email,
                'name': name,
                'amount': str(amount),
                'trip_id': trip_id
            },
            receipt_email=email
        )
        
        # Create payment record in database
        payment = Payment(
            payment_intent_id=intent.id,
            email=email,
            name=name,
            amount=intent.amount,
            status=intent.status,
            trip_id=trip_id
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


@app.route('/update-payment-intent', methods=['POST'])
def update_payment():
    try:
        data = json.loads(request.data)
        
        # Get payment intent ID, new amount, and email from the request data
        payment_intent_id = data.get('paymentIntentId')
        amount = float(data.get('amount', 135.00))
        email = data.get('email', '')
        name = data.get('name', '')
        
        # Update the existing PaymentIntent
        intent = stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=calculate_order_amount(amount),
            metadata={
                'email': email,
                'name': name,
                'amount': str(amount)
            },
            receipt_email=email
        )

        # Update payment record in database
        payment = Payment.query.filter_by(payment_intent_id=payment_intent_id).first()
        if payment:
            payment.amount = intent.amount
            payment.email = email
            payment.name = name
            payment.status = intent.status
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


@app.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    # Update payment status in database
    payment = Payment.query.filter_by(payment_intent_id=data_object['id']).first()
    if payment:
        if event_type == 'payment_intent.amount_capturable_updated':
            payment.status = data_object['status']
            print('💳 Charging the card for: ' + str(data_object['amount_capturable']))
            intent = stripe.PaymentIntent.capture(data_object['id'])
            
        elif event_type == 'payment_intent.succeeded':
            payment.status = 'succeeded'
            print('✅ Payment received!')
            
        elif event_type == 'payment_intent.payment_failed':
            payment.status = 'failed'
            print('❌ Payment failed.')
        
        db.session.commit()

    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(port=os.getenv('PORT', 5000))
