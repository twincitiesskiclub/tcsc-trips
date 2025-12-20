from enum import Enum

# Timezone
TIMEZONE = 'America/Chicago'
ALLOWED_EMAIL_DOMAIN = '@twincitiesskiclub.org'

# Date formats
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%dT%H:%M'

# Currency
CENTS_PER_DOLLAR = 100
MIN_PRICE_CENTS = 100  # Minimum price: $1.00
CURRENCY = 'usd'


class MemberType(Enum):
    NEW = "NEW"
    RETURNING = "RETURNING"
    FORMER = "FORMER"


class UserStatus:
    """Global user status across all seasons"""
    PENDING = 'PENDING'      # Registered, awaiting lottery
    ACTIVE = 'ACTIVE'        # Current season member
    ALUMNI = 'ALUMNI'        # Not active this season (formerly INACTIVE)
    DROPPED = 'DROPPED'      # Removed for cause

    ALL = [PENDING, ACTIVE, ALUMNI, DROPPED]


class UserSeasonStatus:
    """Per-season user status (expanded for lottery tracking)"""
    PENDING_LOTTERY = 'PENDING_LOTTERY'      # Registered, awaiting lottery
    ACTIVE = 'ACTIVE'                        # Accepted member
    DROPPED_LOTTERY = 'DROPPED_LOTTERY'      # Lost lottery -> priority next time
    DROPPED_VOLUNTARY = 'DROPPED_VOLUNTARY'  # Withdrew by choice
    DROPPED_CAUSE = 'DROPPED_CAUSE'          # Removed for cause

    ALL = [PENDING_LOTTERY, ACTIVE, DROPPED_LOTTERY, DROPPED_VOLUNTARY, DROPPED_CAUSE]


class StripeEvent:
    """Stripe webhook event types"""
    PAYMENT_CAPTURABLE = 'payment_intent.amount_capturable_updated'
    PAYMENT_SUCCEEDED = 'payment_intent.succeeded'
    PAYMENT_CANCELED = 'payment_intent.canceled'


class PaymentType:
    """Type of payment - what entity is being paid for"""
    SEASON = 'season'
    TRIP = 'trip'
    SOCIAL_EVENT = 'social_event'

    ALL = [SEASON, TRIP, SOCIAL_EVENT]


# Registration form valid values (must match season_register.html)
VALID_TSHIRT_SIZES = {'XS', 'S', 'M', 'L', 'XL', '2XL'}
VALID_TECHNIQUES = {'classic', 'skate', 'no_preference'}
VALID_EXPERIENCE_LEVELS = {'1-3', '3-7', '7+'}
VALID_MEMBER_STATUSES = {'new', 'returning_former'}

# Field length limits
MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 500
MAX_PHONE_LENGTH = 30
MAX_PRONOUNS_LENGTH = 50
MAX_RELATION_LENGTH = 100

# Age limits for date of birth validation
MIN_MEMBER_AGE = 16
MAX_MEMBER_AGE = 120