"""Member-facing SMS. One entry point; a failed text never fails its caller."""
import os

import yaml
from flask import current_app

from app.models import db
from app.verify.providers import ProviderError, twilio_send_sms

_TEMPLATES = None


def _templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        path = os.path.join(current_app.root_path, '..', 'config', 'sms.yaml')
        with open(path) as fh:
            _TEMPLATES = yaml.safe_load(fh)['templates']
    return _TEMPLATES


def send_sms(user, template_key, **kwargs):
    """Render config/sms.yaml template_key and text it to user.phone_e164.

    Returns True on send, False on skip or failure. Never raises.
    """
    try:
        if not user.phone_e164 or user.sms_opt_out:
            return False
        body = _templates()[template_key].format(**kwargs)
        twilio_send_sms(user.phone_e164, body)
        current_app.logger.info("sms: sent %s to user %s", template_key, user.id)
        return True
    except ProviderError as exc:
        if exc.code == 21610:  # recipient has replied STOP
            user.sms_opt_out = True
            db.session.commit()
        current_app.logger.warning(
            "sms: %s to user %s failed: %s", template_key, user.id, exc)
        return False
    except Exception as exc:
        current_app.logger.warning(
            "sms: %s to user %s failed: %s", template_key, user.id, exc)
        return False
