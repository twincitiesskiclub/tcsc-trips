"""Common utility functions for the TCSC application."""

from datetime import datetime, date
import pytz
import re

from .constants import (
    TIMEZONE, DATE_FORMAT, DATETIME_FORMAT,
    VALID_TSHIRT_SIZES, VALID_TECHNIQUES, VALID_EXPERIENCE_LEVELS, VALID_MEMBER_STATUSES,
    MAX_NAME_LENGTH, MAX_ADDRESS_LENGTH, MAX_PHONE_LENGTH, MAX_PRONOUNS_LENGTH,
    MAX_RELATION_LENGTH, MIN_MEMBER_AGE, MAX_MEMBER_AGE
)

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


def now_central_naive() -> datetime:
    """Get current datetime as naive Central time.

    Use this when comparing against Practice.date and other fields
    stored as naive Central datetimes.
    """
    return datetime.now(CENTRAL_TZ).replace(tzinfo=None)


def format_datetime_central(dt: datetime, fmt: str = '%b %d, %Y %I:%M %p %Z') -> str:
    """Format a datetime in Central timezone.

    For naive datetimes, assumes UTC (correct for created_at, updated_at,
    expires_at). Do NOT use for Practice.date which is stored as naive Central.

    Args:
        dt: datetime object (timezone-aware or naive UTC)
        fmt: strftime format string

    Returns:
        Formatted datetime string in Central time
    """
    if dt is None:
        return ''
    # If naive datetime, assume it's UTC (per database storage convention)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
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


# =============================================================================
# Form Validation Functions
# =============================================================================

# Simple email regex - catches obvious errors without being overly strict
EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

# Phone regex - allows common formats: (555) 123-4567, 555-123-4567, 5551234567, +1-555-123-4567
PHONE_REGEX = re.compile(r'^[\d\s\-\+\(\)\.]+$')


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email or not email.strip():
        return False, "Email is required"
    if not EMAIL_REGEX.match(email.strip()):
        return False, "Invalid email format"
    return True, ""


def validate_phone(phone: str, field_name: str = "Phone") -> tuple[bool, str]:
    """Validate phone number format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone or not phone.strip():
        return False, f"{field_name} is required"
    phone = phone.strip()
    if len(phone) > MAX_PHONE_LENGTH:
        return False, f"{field_name} is too long (max {MAX_PHONE_LENGTH} characters)"
    if not PHONE_REGEX.match(phone):
        return False, f"{field_name} contains invalid characters"
    # Must have at least 7 digits (basic phone number)
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 7:
        return False, f"{field_name} must have at least 7 digits"
    return True, ""


def validate_required_string(value: str, field_name: str, max_length: int) -> tuple[bool, str]:
    """Validate a required string field.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{field_name} is required"
    if len(value.strip()) > max_length:
        return False, f"{field_name} is too long (max {max_length} characters)"
    return True, ""


def validate_optional_string(value: str, field_name: str, max_length: int) -> tuple[bool, str]:
    """Validate an optional string field (only checks length if provided).

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value and len(value.strip()) > max_length:
        return False, f"{field_name} is too long (max {max_length} characters)"
    return True, ""


def validate_date_of_birth(dob: date) -> tuple[bool, str]:
    """Validate date of birth is within reasonable range.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not dob:
        return False, "Date of birth is required"

    today = datetime.now(CENTRAL_TZ).date()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    if age < MIN_MEMBER_AGE:
        return False, f"You must be at least {MIN_MEMBER_AGE} years old to register"
    if age > MAX_MEMBER_AGE:
        return False, "Invalid date of birth"
    if dob > today:
        return False, "Date of birth cannot be in the future"

    return True, ""


def validate_choice(value: str, valid_choices: set, field_name: str) -> tuple[bool, str]:
    """Validate a value is one of the allowed choices.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, f"{field_name} is required"
    if value not in valid_choices:
        return False, f"Invalid {field_name.lower()}"
    return True, ""


def validate_registration_form(form: dict, dob: date = None) -> tuple[bool, list[str]]:
    """Validate all registration form fields.

    Args:
        form: Dictionary of form fields (from request.form)
        dob: Parsed date of birth (already converted from string)

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []

    # Email
    valid, msg = validate_email(form.get('email', ''))
    if not valid:
        errors.append(msg)

    # Member status
    valid, msg = validate_choice(form.get('status', ''), VALID_MEMBER_STATUSES, 'Member status')
    if not valid:
        errors.append(msg)

    # Personal info
    valid, msg = validate_required_string(form.get('firstName', ''), 'First name', MAX_NAME_LENGTH)
    if not valid:
        errors.append(msg)

    valid, msg = validate_required_string(form.get('lastName', ''), 'Last name', MAX_NAME_LENGTH)
    if not valid:
        errors.append(msg)

    valid, msg = validate_optional_string(form.get('pronouns', ''), 'Pronouns', MAX_PRONOUNS_LENGTH)
    if not valid:
        errors.append(msg)

    # Date of birth
    if dob:
        valid, msg = validate_date_of_birth(dob)
        if not valid:
            errors.append(msg)

    # Phone
    valid, msg = validate_phone(form.get('phone', ''), 'Phone number')
    if not valid:
        errors.append(msg)

    # Address
    valid, msg = validate_required_string(form.get('address', ''), 'Address', MAX_ADDRESS_LENGTH)
    if not valid:
        errors.append(msg)

    # T-shirt size
    valid, msg = validate_choice(form.get('tshirtSize', ''), VALID_TSHIRT_SIZES, 'T-shirt size')
    if not valid:
        errors.append(msg)

    # Skiing details
    valid, msg = validate_choice(form.get('technique', ''), VALID_TECHNIQUES, 'Preferred technique')
    if not valid:
        errors.append(msg)

    valid, msg = validate_choice(form.get('experience', ''), VALID_EXPERIENCE_LEVELS, 'Ski experience')
    if not valid:
        errors.append(msg)

    # Emergency contact
    valid, msg = validate_required_string(form.get('emergencyName', ''), 'Emergency contact name', MAX_NAME_LENGTH)
    if not valid:
        errors.append(msg)

    valid, msg = validate_required_string(form.get('emergencyRelation', ''), 'Emergency contact relationship', MAX_RELATION_LENGTH)
    if not valid:
        errors.append(msg)

    valid, msg = validate_phone(form.get('emergencyPhone', ''), 'Emergency contact phone')
    if not valid:
        errors.append(msg)

    valid, msg = validate_email(form.get('emergencyEmail', ''))
    if not valid:
        errors.append(f"Emergency contact email: {msg.lower()}")

    return len(errors) == 0, errors
