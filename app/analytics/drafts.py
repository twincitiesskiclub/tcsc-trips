"""Plain data passed between the pure lineage functions. No DB access here."""
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


@dataclass(frozen=True)
class ArchivedMessage:
    channel_id: str
    ts: str
    raw: dict                      # Slack message payload as stored in slack_archive_messages.raw
    replies: tuple = ()            # raw payloads of thread replies, oldest first
    deleted: bool = False
    archive_id: Optional[int] = None


@dataclass(frozen=True)
class TripSignup:
    series_slug: str
    edition_year: int             # Fall/Winter start year
    posted_on: date               # Central date of the sign-up
    slack_uid: Optional[str]
    person_name: Optional[str]
    source_key: str               # "channel:ts" or "trip_registration:<id>"


@dataclass(frozen=True)
class AppPractice:
    id: int
    date: datetime                 # naive Central, as stored in practices.date
    status: str                    # scheduled | cancelled | ...
    is_draft: bool
    slack_channel_id: Optional[str]
    slack_message_ts: Optional[str]
    slack_session_emoji: Optional[str]
    location_name: Optional[str]
    location_spot: Optional[str]
    activities: tuple = ()
    types: tuple = ()
    lead_uids: tuple = ()
    coach_uids: tuple = ()
    plan_emoji: tuple = ()
    button_rsvp_uids: tuple = ()


@dataclass(frozen=True)
class LocationRef:
    id: int
    name: str
    spot: Optional[str]
    lat: Optional[float]
    lon: Optional[float]


@dataclass(frozen=True)
class SeasonRef:
    name: str
    start_date: date
    end_date: date


@dataclass
class SessionDraft:
    session_key: str
    group_key: str
    era: str                       # template | app
    date: date
    start_time: Optional[time]
    title: str
    venue_raw: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_indoor: bool = False
    activities: list = field(default_factory=list)
    workout_types: list = field(default_factory=list)
    activity: str = "Other"
    workout_type: str = "Other"
    kind: str = "practice"
    format: str = "single"
    slot: Optional[str] = None
    rsvp_emoji: Optional[str] = None
    rsvp_emoji_set: list = field(default_factory=list)  # empty uses rsvp_emoji
    status: str = "held"
    channel_id: Optional[str] = None
    source_ts: Optional[str] = None
    source_archive_id: Optional[int] = None
    practice_id: Optional[int] = None
    lead_uids: list = field(default_factory=list)
    coach_uids: list = field(default_factory=list)
    plan_emoji: list = field(default_factory=list)
    category: str = ""
    reported_count: Optional[int] = None
    decline_emoji: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    season_label: str = ""
    day_of_week: str = ""
    rsvp_count: int = 0
    needs_review: bool = False


@dataclass(frozen=True)
class AttendanceDraft:
    session_key: str
    slack_uid: Optional[str]
    role: str                      # rsvp | plan | lead | coach | signup | decline
    emoji: Optional[str]
    slot: Optional[str]
    source: str                    # reaction | button | post_text | app | correction
    person_name: Optional[str] = None


@dataclass
class LineageResult:
    sessions: list                 # SessionDraft with season_label/day_of_week filled by lineage
    attendance: list               # AttendanceDraft
    possible_misses: list          # "channel:ts" of reacted messages that produced no session
