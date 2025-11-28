"""Common utility functions for the TCSC application."""

from datetime import datetime, date
import pytz

from .constants import TIMEZONE, DATE_FORMAT, DATETIME_FORMAT


def normalize_email(email: str) -> str:
    """Normalize email: strip whitespace and convert to lowercase."""
    return email.strip().lower() if email else ""


def parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, DATE_FORMAT).date()


def parse_datetime(datetime_str: str) -> datetime:
    """Parse a datetime string in YYYY-MM-DDTHH:MM format."""
    return datetime.strptime(datetime_str, DATETIME_FORMAT)


def get_current_times() -> dict:
    """Get current time in both Central and UTC timezones.

    Returns:
        dict with 'central' and 'utc' datetime objects
    """
    central = pytz.timezone(TIMEZONE)
    return {
        'central': datetime.now(central),
        'utc': datetime.utcnow()
    }


def get_user_member_type(user) -> str:
    """Determine if a user is 'new' or 'returning' member.

    Args:
        user: User model instance or None

    Returns:
        'returning' if user has been active in a past season, 'new' otherwise
    """
    return 'returning' if user and user.is_returning else 'new'
