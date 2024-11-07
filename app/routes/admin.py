from flask import Blueprint, render_template, jsonify, request
from ..auth import admin_required
from ..models import db, Payment

admin = Blueprint('admin', __name__)

@admin.route('/admin')
@admin_required
def get_admin_page():
    payments = Payment.query.all()
    return render_template('admin.html', payments=payments)