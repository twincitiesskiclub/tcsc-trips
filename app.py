#! /usr/bin/env python3.6

import os
import json
import stripe
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv, find_dotenv
from models import db, Payment

# Configuration Functions
def load_stripe_config():
    load_dotenv(find_dotenv())
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    stripe.api_version = os.getenv('STRIPE_API_VERSION')

def configure_database(app, environment):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    db_paths = {
        'production': '/var/lib/app.db',
        'development': '/var/lib/app.db',
        'testing': os.path.join(base_dir, 'instance', 'test.db')
    }
    
    if environment not in db_paths:
        raise ValueError(f"Invalid FLASK_ENV value: {environment}")
        
    if environment == 'testing':
        os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)
        
    db_path = db_paths[environment]
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    with app.app_context():
        db.create_all()

# Payment Processing Functions
def calculate_order_amount(amount):
    amount_in_cents = int(amount * 100)
    return amount_in_cents if amount_in_cents in [13500, 16000] else 13500

def create_stripe_payment_intent(amount, email, name, trip_id):
    return stripe.PaymentIntent.create(
        amount=calculate_order_amount(amount),
        currency='usd',
        capture_method="manual",
        metadata={
            'email': email,
            'name': name,
            'amount': str(amount),
            'trip_id': trip_id
        },
        receipt_email=email
    )

def save_payment_to_db(intent, email, name, trip_id):
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
    return payment

# Initialize Flask App
app = Flask(__name__, static_folder='static', static_url_path='/static')
load_stripe_config()
configure_database(app, os.getenv('FLASK_ENV', 'development'))

# Route Handlers
@app.route('/')
def get_home_page():
    return render_template('index.html')

@app.route('/training-trip')
def get_training_trip_page():
    return render_template('training-trip.html')

@app.route('/get-stripe-key')
def get_stripe_key():
    return jsonify({'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY')})

@app.route('/create-payment-intent', methods=['POST'])
def create_payment():
    try:
        data = json.loads(request.data)
        email = data.get('email', '')
        name = data.get('name', '')
        amount = float(data.get('amount', 135.00))
        trip_id = request.referrer.split('/')[-1] if request.referrer else 'generic-trip'
        
        intent = create_stripe_payment_intent(amount, email, name, trip_id)
        save_payment_to_db(intent, email, name, trip_id)
        
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
        payment_intent_id = data.get('paymentIntentId')
        amount = float(data.get('amount', 135.00))
        email = data.get('email', '')
        name = data.get('name', '')
        
        intent = stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=calculate_order_amount(amount),
            metadata={'email': email, 'name': name, 'amount': str(amount)},
            receipt_email=email
        )
        
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
    
    try:
        if webhook_secret:
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
            
        handle_webhook_event(data['object'], event['type'])
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def handle_webhook_event(data_object, event_type):
    payment = Payment.query.filter_by(payment_intent_id=data_object['id']).first()
    if not payment:
        return
        
    status_updates = {
        'payment_intent.amount_capturable_updated': data_object['status'],
        'payment_intent.succeeded': 'succeeded',
        'payment_intent.payment_failed': 'failed'
    }
    
    if event_type in status_updates:
        payment.status = status_updates[event_type]
        db.session.commit()

if __name__ == '__main__':
    app.run(port=os.getenv('PORT', 5000))
