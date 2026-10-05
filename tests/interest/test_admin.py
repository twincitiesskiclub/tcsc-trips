import csv
import io

from app.interest import service
from app.interest.models import InterestSignup
from app.models import User, db

from .conftest import TEST_DOMAIN


def add(app, name, email, phone=''):
    with app.app_context():
        service.save_signup({'name': name, 'email': email, 'phone': phone})
        return InterestSignup.query.filter_by(email=email).one().id


def test_page_requires_admin(client):
    resp = client.get('/admin/interest-list')
    assert resp.status_code == 302


def test_page_lists_rows_with_member_status(app, admin_client):
    add(app, 'Pat Prospect', f'pat{TEST_DOMAIN}')
    with app.app_context():
        db.session.add(User(email=f'Mem{TEST_DOMAIN}', first_name='M',
                            last_name='Em', status='ACTIVE'))
        db.session.commit()
    add(app, 'Mem Ber', f'mem{TEST_DOMAIN}')
    html = admin_client.get('/admin/interest-list').get_data(as_text=True)
    assert f'pat{TEST_DOMAIN}' in html
    assert f'mem{TEST_DOMAIN}' in html
    assert 'ACTIVE' in html


def test_csv_has_every_row_and_raw_phone(app, admin_client):
    add(app, 'Pat Prospect', f'pat{TEST_DOMAIN}', '612-555-0101')
    resp = admin_client.get('/admin/interest-list/export.csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    rows = list(csv.DictReader(io.StringIO(resp.get_data(as_text=True))))
    mine = [r for r in rows if r['Email'] == f'pat{TEST_DOMAIN}']
    assert len(mine) == 1
    # Server-normalized phones skip the sanitizer: '+' must not gain a quote.
    assert mine[0]['Phone'] == '+16125550101'
    assert mine[0]['SMS consent'] != ''
    assert set(rows[0]) == {'Name', 'Email', 'Phone', 'Signed up',
                            'SMS consent', 'Member status'}


def test_csv_sanitizes_typed_text(app, admin_client):
    add(app, '=HYPERLINK("http://x")', f'evil{TEST_DOMAIN}')
    rows = list(csv.DictReader(io.StringIO(
        admin_client.get('/admin/interest-list/export.csv').get_data(as_text=True))))
    mine = [r for r in rows if r['Email'] == f'evil{TEST_DOMAIN}']
    assert mine[0]['Name'].startswith("'=")


def test_delete_removes_one_row(app, admin_client):
    keep = add(app, 'Keep', f'keep{TEST_DOMAIN}')
    drop = add(app, 'Drop', f'drop{TEST_DOMAIN}')
    resp = admin_client.post(f'/admin/interest-list/{drop}/delete')
    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(InterestSignup, drop) is None
        assert db.session.get(InterestSignup, keep) is not None


def test_delete_missing_row_is_404(admin_client):
    assert admin_client.post('/admin/interest-list/999999999/delete').status_code == 404
