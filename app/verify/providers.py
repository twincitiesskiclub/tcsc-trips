"""Thin HTTP clients for Twilio Verify, Twilio Messaging, and Resend.

Every function either succeeds or raises ProviderError. Callers own the
policy (rate limits, degradation copy); this module owns transport only.
"""
import requests
from flask import current_app

TIMEOUT = 10


class ProviderError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _twilio_auth():
    key_sid = current_app.config['TWILIO_API_KEY_SID']
    key_secret = current_app.config['TWILIO_API_KEY_SECRET']
    if not key_sid or not key_secret:
        raise ProviderError('Twilio credentials are not configured')
    return (key_sid, key_secret)


def _raise_for_twilio(resp):
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        raise ProviderError(body.get('message', f'HTTP {resp.status_code}'),
                            code=body.get('code'))


def twilio_verify_start(phone_e164):
    sid = current_app.config['TWILIO_VERIFY_SERVICE_SID']
    if not sid:
        raise ProviderError('Twilio Verify is not configured')
    resp = requests.post(
        f'https://verify.twilio.com/v2/Services/{sid}/Verifications',
        auth=_twilio_auth(), data={'To': phone_e164, 'Channel': 'sms'},
        timeout=TIMEOUT)
    _raise_for_twilio(resp)


def twilio_verify_check(phone_e164, code):
    sid = current_app.config['TWILIO_VERIFY_SERVICE_SID']
    if not sid:
        raise ProviderError('Twilio Verify is not configured')
    resp = requests.post(
        f'https://verify.twilio.com/v2/Services/{sid}/VerificationCheck',
        auth=_twilio_auth(), data={'To': phone_e164, 'Code': code},
        timeout=TIMEOUT)
    # A check against an expired/unknown verification returns 404 — treat as
    # a plain wrong-code failure, not an outage.
    if resp.status_code == 404:
        return False
    _raise_for_twilio(resp)
    return resp.json().get('status') == 'approved'


def twilio_send_sms(phone_e164, body):
    account = current_app.config['TWILIO_ACCOUNT_SID']
    service = current_app.config['TWILIO_MESSAGING_SERVICE_SID']
    if not (account and service):
        raise ProviderError('Twilio Messaging is not configured')
    resp = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json',
        auth=_twilio_auth(),
        data={'To': phone_e164, 'MessagingServiceSid': service, 'Body': body},
        timeout=TIMEOUT)
    _raise_for_twilio(resp)


def resend_send_code(email, first_name, code):
    api_key = current_app.config['RESEND_API_KEY']
    if not api_key:
        raise ProviderError('Resend is not configured')
    greeting = f'Hi {first_name}!' if first_name else 'Hi!'
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}'},
        json={
            'from': 'Twin Cities Ski Club <club@tcsc.ski>',
            'to': [email],
            'subject': f'Your TCSC code: {code}',
            'text': (f"{greeting} Here is your Twin Cities Ski Club "
                     f"verification code: {code}. It expires in 10 minutes. "
                     "Didn't request this? Just ignore it."),
        },
        timeout=TIMEOUT)
    if resp.status_code >= 400:
        raise ProviderError(f'Resend HTTP {resp.status_code}')
