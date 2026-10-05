"""Public interest-list signup.

Both the marketing site's /join page and tcsc.ski's own pages post here. The
marketing site is another origin and cannot carry this app's CSRF token, so
the POST is exempt; the worst a forged POST can do is add a row, which a
direct POST could do anyway. Every response is a page on tcsc.ski: no
cross-site redirect.
"""
from flask import Blueprint, render_template, request

from app.interest import service
from app.security import csrf

interest = Blueprint('interest', __name__)


@interest.route('/interest', methods=['GET'])
def interest_form():
    return render_template('interest.html', values={}, errors={})


@interest.route('/interest', methods=['POST'])
@csrf.exempt
def interest_submit():
    if request.form.get(service.HONEYPOT):
        return render_template('interest_thanks.html')
    values, errors = service.validate(request.form)
    if errors:
        return render_template('interest.html', values=values, errors=errors), 400
    service.save_signup(values)
    return render_template('interest_thanks.html')
