"""Admin view of the interest list: table, CSV export, per-row delete."""
import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, url_for

from app.auth import admin_required
from app.interest import service
from app.interest.models import InterestSignup
from app.models import db
from app.routes.admin_events import _sanitize_csv_value
from app.utils import utc_naive_to_central_naive

admin_interest_bp = Blueprint('admin_interest', __name__)

CSV_COLUMNS = ['Name', 'Email', 'Phone', 'Signed up', 'SMS consent', 'Member status']


def _central(dt):
    return utc_naive_to_central_naive(dt).strftime('%Y-%m-%d %H:%M') if dt else ''


@admin_interest_bp.route('/admin/interest-list')
@admin_required
def interest_list():
    return render_template('admin/interest_list.html',
                           rows=service.rows_with_member_status())


@admin_interest_bp.route('/admin/interest-list/export.csv')
@admin_required
def interest_list_csv():
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in service.rows_with_member_status():
        s = r['signup']
        writer.writerow({
            # Name and email are typed by strangers; sanitize them. Phone and
            # timestamps are server-generated, and phones start with '+',
            # which the sanitizer would mangle.
            'Name': _sanitize_csv_value(s.name),
            'Email': _sanitize_csv_value(s.email),
            'Phone': s.phone_e164 or '',
            'Signed up': _central(s.created_at),
            'SMS consent': _central(s.sms_consent_at),
            'Member status': r['member_status'],
        })
    filename = f'interest-list-{date.today().isoformat()}.csv'
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@admin_interest_bp.route('/admin/interest-list/<int:signup_id>/delete', methods=['POST'])
@admin_required
def interest_list_delete(signup_id):
    signup = db.session.get(InterestSignup, signup_id)
    if signup is None:
        abort(404)
    email = signup.email
    db.session.delete(signup)
    db.session.commit()
    flash(f'Removed {email} from the interest list.', 'success')
    return redirect(url_for('admin_interest.interest_list'))
