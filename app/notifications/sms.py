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
    user_id = None
    try:
        with db.session.no_autoflush:
            user_id = user.id  # Cache before potential session issues
        if not user.phone_e164 or user.sms_opt_out:
            return False
        body = _templates()[template_key].format(**kwargs)
        twilio_send_sms(user.phone_e164, body)
        current_app.logger.info("sms: sent %s to user %s", template_key, user_id)
        return True
    except ProviderError as exc:
        if exc.code == 21610:  # recipient has replied STOP
            try:
                user.sms_opt_out = True
                db.session.commit()
            except Exception as commit_exc:
                current_app.logger.warning(
                    "sms: failed to record opt-out for user %s: %s", user_id, commit_exc)
                try:
                    db.session.rollback()
                except Exception as rollback_exc:
                    current_app.logger.warning(
                        "sms: failed to rollback session for user %s: %s", user_id, rollback_exc)
        current_app.logger.warning(
            "sms: %s to user %s failed: %s", template_key, user_id, exc)
        return False
    except Exception as exc:
        # Outermost safety net: covers the user_id cache read above too, so a
        # detached/expired `user` (DetachedInstanceError, transient DB error
        # on attribute refresh) can never escape this function. Don't touch
        # user attributes here -- they may be exactly what's unreadable.
        current_app.logger.warning(
            "sms: %s failed for user_id=%s: %s", template_key, user_id, exc)
        return False
