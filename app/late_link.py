"""Signed, time-limited tokens that grant late-registration access for one email."""
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app

from .utils import normalize_email

SALT = "late-registration"
MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT)


def generate(season_id: int, email: str) -> str:
    """Return a signed token for (season_id, normalized email)."""
    payload = {"season_id": int(season_id), "email": normalize_email(email)}
    return _serializer().dumps(payload)


def verify(token: str) -> dict | None:
    """Return the payload dict if the token is valid and not expired, else None."""
    if not token:
        return None
    try:
        return _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
