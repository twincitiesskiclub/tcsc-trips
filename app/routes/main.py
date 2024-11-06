from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def get_home_page():
    return render_template('index.html')
