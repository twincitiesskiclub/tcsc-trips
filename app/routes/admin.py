from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from ..auth import admin_required
from ..models import db, Payment, Trip
from datetime import datetime

admin = Blueprint('admin', __name__)

@admin.route('/admin')
@admin_required
def get_admin_page():
    return render_template('admin/index.html')

@admin.route('/admin/payments')
@admin_required
def get_admin_payments():
    payments = Payment.query.all()
    return render_template('admin/payments.html', payments=payments)

@admin.route('/admin/trips')
@admin_required
def get_admin_trips():
    trips = Trip.query.order_by(Trip.start_date).all()
    return render_template('admin/trips.html', trips=trips)

@admin.route('/admin/trips/new', methods=['GET', 'POST'])
@admin_required
def new_trip():
    if request.method == 'POST':
        try:
            trip = Trip(
                slug=request.form['slug'],
                name=request.form['name'],
                destination=request.form['destination'],
                max_participants_standard=int(request.form['max_participants_standard']),
                max_participants_extra=int(request.form['max_participants_extra']),
                start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
                end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d'),
                signup_start=datetime.strptime(request.form['signup_start'], '%Y-%m-%dT%H:%M'),
                signup_end=datetime.strptime(request.form['signup_end'], '%Y-%m-%dT%H:%M'),
                price_low=int(float(request.form['price_low']) * 100),  # Convert to cents
                price_high=int(float(request.form['price_high']) * 100),  # Convert to cents
                description=request.form['description'],
                status=request.form['status']
            )
            db.session.add(trip)
            db.session.commit()
            flash('Trip created successfully!', 'success')
            return redirect(url_for('admin.get_admin_page'))
        except Exception as e:
            flash(f'Error creating trip: {str(e)}', 'error')
            return redirect(url_for('admin.new_trip'))
    
    return render_template('admin/trip_form.html', trip=None)

@admin.route('/admin/trips/<int:trip_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    if request.method == 'POST':
        try:
            trip.name = request.form['name']
            trip.destination = request.form['destination']
            trip.max_participants_standard = int(request.form['max_participants_standard'])
            trip.max_participants_extra = int(request.form['max_participants_extra'])
            trip.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            trip.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
            trip.signup_start = datetime.strptime(request.form['signup_start'], '%Y-%m-%dT%H:%M')
            trip.signup_end = datetime.strptime(request.form['signup_end'], '%Y-%m-%dT%H:%M')
            trip.price_low = int(float(request.form['price_low']) * 100)
            trip.price_high = int(float(request.form['price_high']) * 100)
            trip.description = request.form['description']
            trip.status = request.form['status']
            
            db.session.commit()
            flash('Trip updated successfully!', 'success')
            return redirect(url_for('admin.get_admin_trips'))
        except Exception as e:
            flash(f'Error updating trip: {str(e)}', 'error')
            return redirect(url_for('admin.edit_trip', trip_id=trip_id))
    
    return render_template('admin/trip_form.html', trip=trip)

@admin.route('/admin/trips/<int:trip_id>/delete')
@admin_required
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    try:
        db.session.delete(trip)
        db.session.commit()
        flash('Trip deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting trip: {str(e)}', 'error')
    
    return redirect(url_for('admin.get_admin_trips'))