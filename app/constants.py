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
    PENDING = 'pending'
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DROPPED = 'dropped'

    ALL = [PENDING, ACTIVE, INACTIVE, DROPPED]


class UserSeasonStatus:
    """Per-season user status"""
    PENDING_LOTTERY = 'PENDING_LOTTERY'
    ACTIVE = 'ACTIVE'
    DROPPED = 'DROPPED'

    ALL = [PENDING_LOTTERY, ACTIVE, DROPPED] 