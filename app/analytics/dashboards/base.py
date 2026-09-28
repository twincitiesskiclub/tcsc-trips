"""Dashboard blocks, validated GET filters, and read-only data access."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, ClassVar

from sqlalchemy import func
from sqlalchemy.engine import Row
from werkzeug.datastructures import MultiDict

from app import utils
from app.analytics import SYNC_CHANNELS
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.models import AppConfig, db
from app.practices.models import PracticeLocation


@dataclass
class Tile:
    label: str
    value: object
    sub: str = ""


@dataclass
class Tiles:
    kind: ClassVar[str] = "tiles"
    tiles: list[Tile]


@dataclass
class Chart:
    kind: ClassVar[str] = "chart"
    title: str
    description: str
    spec: dict
    rows: list[dict]
    columns: list[tuple[str, str]]


@dataclass
class Table:
    kind: ClassVar[str] = "table"
    title: str
    rows: list[dict]
    columns: list[tuple[str, str]]


@dataclass
class Note:
    kind: ClassVar[str] = "note"
    text: str


@dataclass
class Dashboard:
    slug: str
    title: str
    question: str
    filters: list[str]
    build: Callable
    kinds: tuple = ()


@dataclass
class Filters:
    seasons: list[str] = field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    days: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    workout_types: list[str] = field(default_factory=list)
    location_ids: list[int] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)


DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FORMATS = ("single", "split", "merged")
KINDS = ("practice", "event", "trip")
# URL name, Filters attribute, PracticeSession column.
_FIELDS = (
    ("season", "seasons", "season_label"), ("day_of_week", "days", "day_of_week"),
    ("activity", "activities", "activity"), ("workout_type", "workout_types", "workout_type"),
    ("location", "location_ids", "location_id"), ("format", "formats", "format"),
    ("kind", "kinds", "kind"),
)


def _past_sessions(kinds=()):
    query = PracticeSession.query.filter(
        PracticeSession.date <= utils.today_central(), ~PracticeSession.flags.any("missing_date"))
    if kinds:
        query = query.filter(PracticeSession.kind.in_(kinds))
    return query


def _distinct(column, kinds=()):
    return {value for (value,) in _past_sessions(kinds).with_entities(column).distinct() if value is not None}


def get_filter_domains(kinds=()) -> dict:
    return {attribute: _distinct(getattr(PracticeSession, column), kinds)
            for _, attribute, column in _FIELDS
            if attribute in ("seasons", "activities", "workout_types", "location_ids")}


def _iso(value):
    try:
        # HTML date inputs and shared URLs use the extended ISO form.
        return date.fromisoformat(value) if len(value) == 10 else None
    except ValueError:
        return None


def parse_filters(args: MultiDict, dashboard: Dashboard, domains=None) -> Filters:
    domains = {**(get_filter_domains(dashboard.kinds) if domains is None else domains), "days": set(DAYS),
               "formats": set(FORMATS), "kinds": set(KINDS)}
    result = Filters()
    for name, attribute, _ in _FIELDS:
        if name not in dashboard.filters:
            continue
        values = []
        for value in args.getlist(name):
            if attribute == "location_ids":
                try:
                    value = int(value)
                except ValueError:
                    continue
            if value in domains[attribute] and value not in values:
                values.append(value)
        setattr(result, attribute, values)
    if "date_range" in dashboard.filters:
        result.date_from = _iso(args.get("date_from", ""))
        result.date_to = _iso(args.get("date_to", ""))
    if dashboard.kinds:
        result.kinds = list(dashboard.kinds)
    return result


def apply_filters(query, filters):
    for _, attribute, column in _FIELDS:
        values = getattr(filters, attribute)
        if values:
            query = query.filter(getattr(PracticeSession, column).in_(values))
    if filters.date_from is not None:
        query = query.filter(PracticeSession.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(PracticeSession.date <= filters.date_to)
    return query


def load_sessions(filters) -> list[PracticeSession]:
    return apply_filters(_past_sessions(), filters).order_by(
        PracticeSession.date, PracticeSession.start_time, PracticeSession.id).all()


def load_attendance(session_ids: list[int], role="rsvp") -> list[Row]:
    if not session_ids:
        return []
    role_filter = PracticeAttendance.role.in_(role) if isinstance(role, tuple) else PracticeAttendance.role == role
    return PracticeAttendance.query.with_entities(
        PracticeAttendance.session_id, PracticeAttendance.slack_uid,
        PracticeAttendance.person_key, PracticeAttendance.user_id,
        PracticeAttendance.slot, PracticeAttendance.role,
    ).filter(
        PracticeAttendance.session_id.in_(session_ids), role_filter
    ).order_by(PracticeAttendance.id).all()


def filter_options(dashboard, domains=None) -> dict:
    domains = get_filter_domains(dashboard.kinds) if domains is None else domains
    locations = _past_sessions(dashboard.kinds).outerjoin(
        PracticeLocation, PracticeLocation.id == PracticeSession.location_id).with_entities(
        PracticeSession.location_id, PracticeSession.location_name, PracticeLocation.spot).filter(
        PracticeSession.location_id.isnot(None)).distinct().all()
    days = _distinct(PracticeSession.day_of_week, dashboard.kinds)
    formats = _distinct(PracticeSession.format, dashboard.kinds)
    kinds = _distinct(PracticeSession.kind, dashboard.kinds)
    location_labels = set()
    for id_, name, spot in locations:
        label = name or f"Location {id_}"
        location_labels.add((id_, f"{label} - {spot}" if spot else label))
    # Same-year fall/winter comes after spring/summer; labels begin with the year.
    seasons = sorted(domains["seasons"], key=lambda value: (
        value[:4], "Fall/Winter" in value, value), reverse=True)
    return {"seasons": seasons, "activities": sorted(domains["activities"]),
            "workout_types": sorted(domains["workout_types"]),
            "locations": sorted(location_labels, key=lambda item: (item[1], item[0])),
            "days": [value for value in DAYS if value in days],
            "formats": [value for value in FORMATS if value in formats],
            "kinds": [value for value in KINDS if value in kinds]}


def footer() -> dict:
    status = AppConfig.get("analytics_sync_status")
    if status is not None:
        latest = max((datetime.fromisoformat(status[channel]) for channel in SYNC_CHANNELS
                      if channel in status), default=None)
    else:
        latest = db.session.query(func.max(SlackArchiveMessage.synced_at)).scalar()
    return {"data_through": utils.format_datetime_central(latest) if latest else None,
            "needs_review": PracticeSession.query.filter_by(needs_review=True).count()}
