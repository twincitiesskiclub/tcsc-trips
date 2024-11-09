from flask import Flask
from .config import load_stripe_config, configure_database
from .routes.main import main
from .routes.trips import trips
from .routes.payments import payments
from .routes.admin import admin
from .routes.auth import auth
from .auth import init_oauth
from .models import db
from flask_migrate import Migrate
import os

def create_app(environment=None):
    if environment is None:
        environment = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.secret_key = os.getenv('FLASK_SECRET_KEY')
    
    load_stripe_config()
    configure_database(app, environment)
    init_oauth(app)
    
    db.init_app(app)
    #migrate = Migrate(app, db)
    
    app.register_blueprint(main)
    app.register_blueprint(trips)
    app.register_blueprint(payments)
    app.register_blueprint(admin)
    app.register_blueprint(auth)
    
    with app.app_context():
        db.create_all()
        
    return app
