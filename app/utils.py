"""Common utility functions for the TCSC application."""

from datetime import datetime, date
import pytz

from .constants import TIMEZONE, DATE_FORMAT, DATETIME_FORMAT

# Pre-configured timezone object for Central time
CENTRAL_TZ = pytz.timezone(TIMEZONE)


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
    return {
        'central': datetime.now(CENTRAL_TZ),
        'utc': datetime.utcnow()
    }


def format_datetime_central(dt: datetime, fmt: str = '%b %d, %Y %I:%M %p %Z') -> str:
    """Format a datetime in Central timezone.

    Args:
        dt: datetime object (timezone-aware or naive UTC)
        fmt: strftime format string

    Returns:
        Formatted datetime string in Central time
    """
    if dt is None:
        return ''
    return dt.astimezone(CENTRAL_TZ).strftime(fmt)


def today_central() -> date:
    """Get today's date in Central timezone.

    Use this for Date columns that represent 'the day the user did something'
    (registration_date, payment_date) rather than datetime.utcnow().date().
    """
    return datetime.now(CENTRAL_TZ).date()


def get_user_member_type(user) -> str:
    """Determine if a user is 'new' or 'returning' member.

    Args:
        user: User model instance or None

    Returns:
        'returning' if user has been active in a past season, 'new' otherwise
    """
    return 'returning' if user and user.is_returning else 'new'
