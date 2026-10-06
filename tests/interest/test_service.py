from unittest.mock import patch

from app.interest import service
from app.interest.models import InterestSignup
from app.models import User, db

from .conftest import TEST_DOMAIN

EMAIL = f'sam{TEST_DOMAIN}'


def form(**overrides):
    base = {'name': 'Sam Skier', 'email': EMAIL, 'phone': ''}
    base.update(overrides)
    return base


def test_validate_accepts_minimal_form(app):
    values, errors = service.validate(form())
    assert errors == {}
    assert values == {'name': 'Sam Skier', 'email': EMAIL, 'phone': ''}


def test_validate_trims_and_keeps_typed_values(app):
    values, errors = service.validate(form(name='  Sam  ', phone=' 612-555-0101 '))
    assert errors == {}
    assert values['name'] == 'Sam'
    assert values['phone'] == '612-555-0101'


def test_validate_requires_name_and_email(app):
    _, errors = service.validate({'name': ' ', 'email': ''})
    assert set(errors) == {'name', 'email'}


def test_validate_rejects_malformed_email(app):
    for bad in ('sam', 'sam@', '@x.com', 'sam@localhost'):
        _, errors = service.validate(form(email=bad))
        assert 'email' in errors, bad


def test_validate_rejects_bad_phone(app):
    _, errors = service.validate(form(phone='12345'))
    assert 'phone' in errors


def test_validate_rejects_oversized_fields(app):
    _, errors = service.validate(form(name='x' * 201, email='x' * 250 + TEST_DOMAIN))
    assert set(errors) == {'name', 'email'}
    # Errors say how to fix the field, not just what is wrong.
    assert errors['name'] == 'Use 200 characters or fewer.'
    assert errors['email'] == 'Use an email address under 255 characters.'


def test_save_creates_row_without_phone(app):
    with app.app_context():
        service.save_signup(form())
        row = InterestSignup.query.filter_by(email=EMAIL).one()
        assert row.name == 'Sam Skier'
        assert row.phone_e164 is None
        assert row.sms_consent_at is None
        assert row.created_at is not None


def test_save_with_phone_stamps_consent(app):
    with app.app_context():
        service.save_signup(form(phone='(612) 555-0101'))
        row = InterestSignup.query.filter_by(email=EMAIL).one()
        assert row.phone_e164 == '+16125550101'
        assert row.sms_consent_at is not None


def test_save_upserts_on_email_case_and_clears_dropped_phone(app):
    with app.app_context():
        service.save_signup(form(phone='612-555-0101'))
        service.save_signup(form(name='Samantha', email=EMAIL.upper(), phone=''))
        rows = InterestSignup.query.filter_by(email=EMAIL).all()
        assert len(rows) == 1
        assert rows[0].name == 'Samantha'
        assert rows[0].phone_e164 is None
        assert rows[0].sms_consent_at is None


def test_save_survives_a_concurrent_insert(app):
    """Two submits of one new email can both miss the lookup; the second
    insert hits the unique constraint and must not raise."""
    with app.app_context():
        service.save_signup(form())
        with patch.object(service, '_existing', return_value=None):
            service.save_signup(form(name='Second'))
        assert InterestSignup.query.filter_by(email=EMAIL).count() == 1


def test_member_status_matches_email_case_insensitively(app):
    with app.app_context():
        db.session.add(User(email=f'Sam{TEST_DOMAIN}', first_name='Sam',
                            last_name='Member', status='ACTIVE'))
        db.session.commit()
        service.save_signup(form())
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == 'ACTIVE'


def test_member_status_matches_phone(app):
    with app.app_context():
        db.session.add(User(email=f'other{TEST_DOMAIN}', first_name='O',
                            last_name='Ther', status='ALUMNI',
                            phone_e164='+16125550199'))
        db.session.commit()
        service.save_signup(form(phone='612-555-0199'))
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == 'ALUMNI'


def test_member_status_blank_without_match(app):
    with app.app_context():
        service.save_signup(form())
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == ''


def test_validate_rejects_junk_characters_in_email(app):
    for bad in ('a b@x.com', '<b>x</b>@x.com', 'a@b@x.com', 'sam@.x.com', 'sam@x.com.'):
        _, errors = service.validate(form(email=bad))
        assert 'email' in errors, bad


def test_validate_accepts_common_email_shapes(app):
    for good in ('first.last+tag@mail.example.co.uk', "o'brien@x.org"):
        _, errors = service.validate(form(email=good))
        assert 'email' not in errors, good


def test_honeypot_name_is_not_an_autofill_target():
    # Password managers and contact autofill fill fields with these names. A
    # filled honeypot silently drops a real signup behind a thanks page.
    assert service.HONEYPOT not in {
        'website', 'url', 'homepage', 'company', 'organization', 'fax',
        'address', 'phone2', 'middle_name', 'nickname',
    }
