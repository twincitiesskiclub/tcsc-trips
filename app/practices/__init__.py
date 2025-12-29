# Practice Management Module
# Part of TCSC Trips application

# Import models
from .models import (
    SocialLocation,
    PracticeLocation,
    PracticeActivity,
    PracticeType,
    Practice,
    PracticeLead,
    PracticeRSVP,
    CancellationRequest,
)

from .interfaces import (
    # Location/Venue contracts
    PracticeLocationInfo,
    SocialLocationInfo,
    # Activity/Type contracts
    PracticeActivityInfo,
    PracticeTypeInfo,
    # Lead/Role contracts
    PracticeLeadInfo,
    # Practice contracts
    PracticeInfo,
    PracticeCreate,
    PracticeUpdate,
    # Weather contracts
    WeatherCheckRequest,
    WeatherConditions,
    WeatherAlert,
    # Trail contracts
    TrailCondition,
    TrailConditionsRequest,
    # Event conflict contracts
    EventConflict,
    EventConflictRequest,
    # Skipper/Decision contracts
    PracticeEvaluation,
    ThresholdViolation,
    CancellationProposal,
    CancellationDecision,
    # RSVP/Attendance contracts
    RSVPInfo,
    AttendanceInfo,
    # Status enums
    PracticeStatus,
    CancellationStatus,
    RSVPStatus,
    LeadRole,
)

from .service import (
    convert_social_location_to_info,
    convert_practice_location_to_info,
    convert_activity_to_info,
    convert_type_to_info,
    convert_lead_to_info,
    convert_practice_to_info,
    convert_cancellation_to_proposal,
)

__all__ = [
    # Models
    'SocialLocation',
    'PracticeLocation',
    'PracticeActivity',
    'PracticeType',
    'Practice',
    'PracticeLead',
    'PracticeRSVP',
    'CancellationRequest',
    # Location/Venue
    'PracticeLocationInfo',
    'SocialLocationInfo',
    # Activity/Type
    'PracticeActivityInfo',
    'PracticeTypeInfo',
    # Lead/Role
    'PracticeLeadInfo',
    # Practice
    'PracticeInfo',
    'PracticeCreate',
    'PracticeUpdate',
    # Weather
    'WeatherCheckRequest',
    'WeatherConditions',
    'WeatherAlert',
    # Trail
    'TrailCondition',
    'TrailConditionsRequest',
    # Event conflicts
    'EventConflict',
    'EventConflictRequest',
    # Skipper/Decision
    'PracticeEvaluation',
    'ThresholdViolation',
    'CancellationProposal',
    'CancellationDecision',
    # RSVP/Attendance
    'RSVPInfo',
    'AttendanceInfo',
    # Status enums
    'PracticeStatus',
    'CancellationStatus',
    'RSVPStatus',
    'LeadRole',
    # Service functions
    'convert_social_location_to_info',
    'convert_practice_location_to_info',
    'convert_activity_to_info',
    'convert_type_to_info',
    'convert_lead_to_info',
    'convert_practice_to_info',
    'convert_cancellation_to_proposal',
]
