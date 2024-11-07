from flask import Flask
from .config import load_stripe_config, configure_database
from .routes.main import main
from .routes.trips import trips
from .routes.payments import payments
from .routes.admin import admin
from .models import db
import os

def create_app(environment=None):
    if environment is None:
        environment = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    
    load_stripe_config()
    configure_database(app, environment)
    
    db.init_app(app)
    
    app.register_blueprint(main)
    app.register_blueprint(trips)
    app.register_blueprint(payments)
    app.register_blueprint(admin)
    
    with app.app_context():
        db.create_all()
        
    return app
