from flask import Blueprint, render_template, request, flash, redirect, url_for
from ..models import db, Season, UserSeason
from datetime import datetime
import pytz

registration = Blueprint('registration', __name__)

@registration.route('/register', methods=['GET', 'POST'])
def register():
    # Get current time in US Central timezone
    central = pytz.timezone('America/Chicago')
    current_time = datetime.now(central)
    
    # Get current active season
    current_season = Season.query.filter(
        Season.start_date <= current_time.date(),
        Season.end_date >= current_time.date()
    ).first()

    if request.method == 'POST':
        try:
            # Create new UserSeason registration
            user_season = UserSeason(
                season_id=current_season.id,
                registration_type=request.form['status'],
                registration_date=current_time.date(),
                status='pending'
            )
            
            # Add additional user info to the database
            # This would require creating a User model and adding the fields
            
            db.session.add(user_season)
            db.session.commit()
            
            flash('Registration submitted successfully!', 'success')
            return redirect(url_for('main.get_home_page'))
            
        except Exception as e:
            flash(f'Error submitting registration: {str(e)}', 'error')
            return redirect(url_for('registration.register'))

    return render_template('register.html', season=current_season) 