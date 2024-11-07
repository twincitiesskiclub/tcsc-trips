from flask import Blueprint, render_template, jsonify, request
import json
import stripe
import os
from ..models import db, Payment

admin = Blueprint('admin', __name__)

@admin.route('/admin')
def get_admin_page():
    payments = Payment.query.all()
    return render_template('admin.html', payments=payments)