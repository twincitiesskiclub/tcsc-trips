"""
Shared interface contracts for the Practice Management System.

All modules use these dataclasses for type-safe communication:
- Module 1: Core Models (produces PracticeInfo, LocationInfo, etc.)
- Module 2: Airtable Migration (produces data matching these contracts)
- Module 3: Weather/Trails (produces WeatherConditions, TrailCondition)
- Module 4: Slack Extension (consumes all contracts for Block Kit rendering)
- Module 5: Skipper Engine (produces PracticeEvaluation, CancellationProposal)
- Module 6: Admin UI (consumes PracticeInfo, produces PracticeCreate/Update)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# =============================================================================
# Status Enums
# =============================================================================

class PracticeStatus(str, Enum):
    """Practice lifecycle status."""
    SCHEDULED = 'scheduled'
    CONFIRMED = 'confirmed'      # Lead confirmed, workout posted
    IN_PROGRESS = 'in_progress'  # Currently happening
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class CancellationStatus(str, Enum):
    """Cancellation proposal status (requires human approval)."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXPIRED = 'expired'  # Timeout reached, fail-open (practice continues)


class RSVPStatus(str, Enum):
    """Member RSVP status."""
    GOING = 'going'
    NOT_GOING = 'not_going'
    MAYBE = 'maybe'


class LeadRole(str, Enum):
    """Role types for practice assignments."""
    LEAD = 'lead'      # Primary practice lead
    ASSIST = 'assist'  # Assistant/helper
    COACH = 'coach'    # Coach providing workout


# =============================================================================
# Location Contracts
# =============================================================================

@dataclass
class SocialLocationInfo:
    """Post-practice social venue information."""
    id: int
    name: str
    address: Optional[str] = None
    google_maps_url: Optional[str] = None


@dataclass
class PracticeLocationInfo:
    """Practice venue with coordinates for weather API."""
    id: int
    name: str                            # e.g., "Theodore Wirth"
    spot: Optional[str] = None           # e.g., "Trailhead parking lot"
    address: Optional[str] = None
    google_maps_url: Optional[str] = None
    latitude: Optional[float] = None     # For NWS weather API
    longitude: Optional[float] = None
    parking_notes: Optional[str] = None
    airtable_id: Optional[str] = None    # For migration reference


# =============================================================================
# Activity & Type Contracts
# =============================================================================

@dataclass
class PracticeActivityInfo:
    """Activity type with gear requirements (e.g., Classic Skiing, Skate Skiing)."""
    id: int
    name: str
    gear_required: list[str] = field(default_factory=list)  # e.g., ["classic skis", "poles"]
    airtable_id: Optional[str] = None


@dataclass
class PracticeTypeInfo:
    """Workout type with fitness goals (e.g., Intervals, Distance, Technique)."""
    id: int
    name: str
    fitness_goals: list[str] = field(default_factory=list)  # e.g., ["Threshold", "VO2 Max"]
    has_intervals: bool = False
    airtable_id: Optional[str] = None


# =============================================================================
# Lead/Role Contracts
# =============================================================================

@dataclass
class PracticeLeadInfo:
    """Assignment of a user to a practice role."""
    id: int
    practice_id: int
    user_id: int
    display_name: str = ''
    slack_user_id: Optional[str] = None
    email: Optional[str] = None
    role: LeadRole = LeadRole.LEAD
    confirmed: bool = False
    confirmed_at: Optional[datetime] = None


# =============================================================================
# Practice Contracts
# =============================================================================

@dataclass
class PracticeInfo:
    """Complete practice information (read contract)."""
    id: int
    date: datetime
    day_of_week: str                     # e.g., "Tuesday"
    status: PracticeStatus

    # Location
    location: Optional[PracticeLocationInfo] = None
    social_location: Optional[SocialLocationInfo] = None

    # Activities and types (many-to-many)
    activities: list[PracticeActivityInfo] = field(default_factory=list)
    practice_types: list[PracticeTypeInfo] = field(default_factory=list)

    # Workout descriptions (rich text from Airtable)
    warmup_description: Optional[str] = None
    workout_description: Optional[str] = None
    cooldown_description: Optional[str] = None

    # Flags
    has_social: bool = False
    is_dark_practice: bool = False       # Evening practice requiring lights

    # Assignments
    leads: list[PracticeLeadInfo] = field(default_factory=list)

    # Slack integration
    slack_message_ts: Optional[str] = None
    slack_channel_id: Optional[str] = None

    # Cancellation
    cancellation_reason: Optional[str] = None

    # Metadata
    airtable_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PracticeCreate:
    """Create a new practice (write contract)."""
    date: datetime
    location_id: int
    activity_ids: list[int] = field(default_factory=list)
    type_ids: list[int] = field(default_factory=list)
    warmup_description: Optional[str] = None
    workout_description: Optional[str] = None
    cooldown_description: Optional[str] = None
    has_social: bool = False
    is_dark_practice: bool = False
    lead_user_ids: list[int] = field(default_factory=list)
    coach_user_ids: list[int] = field(default_factory=list)
    assist_user_ids: list[int] = field(default_factory=list)


@dataclass
class PracticeUpdate:
    """Update an existing practice (write contract)."""
    id: int
    date: Optional[datetime] = None
    location_id: Optional[int] = None
    activity_ids: Optional[list[int]] = None
    type_ids: Optional[list[int]] = None
    warmup_description: Optional[str] = None
    workout_description: Optional[str] = None
    cooldown_description: Optional[str] = None
    has_social: Optional[bool] = None
    is_dark_practice: Optional[bool] = None
    status: Optional[PracticeStatus] = None
    cancellation_reason: Optional[str] = None


# =============================================================================
# Weather Contracts (Module 3 → Modules 4, 5)
# =============================================================================

@dataclass
class WeatherCheckRequest:
    """Request weather data for a location and time."""
    latitude: float
    longitude: float
    target_datetime: datetime
    location_name: Optional[str] = None  # For logging/display


@dataclass
class WeatherAlert:
    """Weather alert from NWS API."""
    event: str                           # e.g., "Winter Storm Warning"
    severity: str                        # minor, moderate, severe, extreme
    headline: str
    description: str
    effective: datetime
    expires: datetime


@dataclass
class WeatherConditions:
    """Weather conditions at a specific time and location."""
    temperature_f: float
    feels_like_f: float                  # Wind chill / heat index
    wind_speed_mph: float
    wind_gust_mph: Optional[float] = None
    wind_direction: Optional[str] = None  # e.g., "NW"
    precipitation_chance: float = 0.0     # 0-100 percent
    precipitation_type: Optional[str] = None  # rain, snow, sleet, etc.
    conditions_summary: str = ''          # e.g., "Partly Cloudy"
    humidity: Optional[float] = None      # 0-100 percent
    visibility_miles: Optional[float] = None

    # Calculated/derived
    has_lightning_threat: bool = False
    is_extreme_cold: bool = False         # Below threshold
    is_extreme_heat: bool = False         # Above threshold

    # Alert info
    alerts: list[WeatherAlert] = field(default_factory=list)

    # Metadata
    forecast_time: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    source: str = 'NWS'


# =============================================================================
# Trail Condition Contracts (Module 3 → Modules 4, 5)
# =============================================================================

@dataclass
class TrailConditionsRequest:
    """Request trail conditions for a location."""
    location_name: str                   # e.g., "Theodore Wirth"
    # Optional: could add coordinates for fuzzy matching


@dataclass
class TrailCondition:
    """Trail condition report from SkinnySkI or other source."""
    location: str
    trails_open: str                     # 'all', 'most', 'partial', 'closed', 'unknown'
    ski_quality: str                     # 'excellent', 'good', 'fair', 'poor', 'b_skis', 'rock_skis'
    groomed: bool = False
    groomed_for: Optional[str] = None    # 'classic', 'skate', 'both'
    snow_depth_inches: Optional[float] = None
    new_snow_inches: Optional[float] = None
    report_date: Optional[datetime] = None
    report_source: str = 'SkinnySkI'
    report_url: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# Event Conflict Contracts (Module 3 → Modules 4, 5)
# =============================================================================

@dataclass
class EventConflictRequest:
    """Request to check for event conflicts."""
    date: datetime
    location_name: Optional[str] = None  # Check specific venue


@dataclass
class EventConflict:
    """Conflicting event that may affect practice."""
    name: str                            # e.g., "City of Lakes Loppet"
    event_type: str                      # 'race', 'clinic', 'venue_closure', etc.
    date: datetime
    location: Optional[str] = None
    affects_practice: bool = True        # Whether this blocks our practice
    source: str = ''                     # e.g., "SkinnySkI", "venue_calendar"
    url: Optional[str] = None
    notes: Optional[str] = None


# =============================================================================
# Skipper Decision Contracts (Module 5 → Modules 4, 6)
# =============================================================================

@dataclass
class ThresholdViolation:
    """A specific threshold that was violated."""
    threshold_name: str                  # e.g., "min_temperature", "wind_chill"
    threshold_value: float               # The limit
    actual_value: float                  # What we measured
    severity: str = 'warning'            # 'warning', 'critical'
    message: str = ''                    # Human-readable explanation


@dataclass
class PracticeEvaluation:
    """Skipper's evaluation of a practice's conditions."""
    practice_id: int
    evaluated_at: datetime

    # Data sources
    weather: Optional[WeatherConditions] = None
    trail_conditions: Optional[TrailCondition] = None
    event_conflicts: list[EventConflict] = field(default_factory=list)
    air_quality: Optional[dict] = None  # AirQualityInfo from air_quality.py

    # Lead/coach status
    has_confirmed_lead: bool = False
    has_posted_workout: bool = False

    # Threshold evaluation
    violations: list[ThresholdViolation] = field(default_factory=list)

    # Overall assessment
    is_go: bool = True                   # Practice can proceed
    recommendation: str = ''             # LLM-generated summary
    confidence: float = 1.0              # 0-1 confidence in assessment


@dataclass
class CancellationProposal:
    """Proposal to cancel a practice (requires human approval)."""
    id: int
    practice_id: int
    proposed_at: datetime
    reason_type: str                     # 'weather', 'trail_conditions', 'no_lead', 'event_conflict'
    reason_summary: str                  # Human-readable summary
    status: CancellationStatus = CancellationStatus.PENDING

    # Slack integration
    slack_message_ts: Optional[str] = None
    slack_channel_id: Optional[str] = None

    # Decision tracking
    decided_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    decided_by_slack_uid: Optional[str] = None
    decision_notes: Optional[str] = None

    # Timeout
    expires_at: Optional[datetime] = None
    evaluation: Optional[PracticeEvaluation] = None


@dataclass
class CancellationDecision:
    """Response to a cancellation proposal."""
    proposal_id: int
    approved: bool
    decided_by_slack_uid: str
    decided_at: datetime
    notes: Optional[str] = None


# =============================================================================
# RSVP/Attendance Contracts (Modules 4, 6)
# =============================================================================

@dataclass
class RSVPInfo:
    """Member RSVP for a practice."""
    id: int
    practice_id: int
    user_id: int
    status: RSVPStatus
    responded_at: datetime
    slack_user_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class AttendanceInfo:
    """Actual attendance record (post-practice)."""
    id: int
    practice_id: int
    user_id: int
    attended: bool
    marked_at: datetime
    marked_by_user_id: Optional[int] = None


# =============================================================================
# Daylight Contracts (Module 3)
# =============================================================================

@dataclass
class DaylightInfo:
    """Sunrise/sunset information for a location and date."""
    date: datetime
    latitude: float
    longitude: float
    sunrise: datetime
    sunset: datetime
    civil_twilight_begin: datetime
    civil_twilight_end: datetime
    day_length_hours: float
