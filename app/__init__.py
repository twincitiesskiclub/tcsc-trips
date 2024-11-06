from flask import Flask
from .config import load_stripe_config, configure_database
from .routes.main import main
from .routes.trips import trips
from .routes.payments import payments
from .models import db
import os

def create_app(environment=None):
    # If environment isn't explicitly passed, get it from FLASK_ENV
    if environment is None:
        environment = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    
    # Configure app
    load_stripe_config()
    configure_database(app, environment)
    
    # Initialize database
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main)
    app.register_blueprint(trips)
    app.register_blueprint(payments)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        
    return app

# This allows for direct running of the app with debug mode
if __name__ == '__main__':
    app = create_app()
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug)
