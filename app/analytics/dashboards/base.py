"""Dashboard blocks, validated GET filters, and read-only data access."""
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, ClassVar

from sqlalchemy import func
from sqlalchemy.engine import Row
from werkzeug.datastructures import MultiDict

from app import utils
from app.analytics import CATEGORIES
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.models import db


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
    fixed: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)


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
    categories: list[str] = field(default_factory=list)


FILTER_NAMES = ("season", "date_range", "day_of_week", "activity", "workout_type", "location", "format", "kind", "category")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FORMATS = ("single", "split", "merged")
KINDS = ("practice", "event", "trip")
# URL name, Filters attribute, PracticeSession column.
_FIELDS = (
    ("season", "seasons", "season_label"), ("day_of_week", "days", "day_of_week"),
    ("activity", "activities", "activity"), ("workout_type", "workout_types", "workout_type"),
    ("location", "location_ids", "location_id"), ("format", "formats", "format"),
    ("kind", "kinds", "kind"), ("category", "categories", "category"),
)


def _past_sessions():
    return PracticeSession.query.filter(
        PracticeSession.date <= utils.today_central(), ~PracticeSession.flags.any("missing_date"))


def _distinct(column):
    return {value for (value,) in _past_sessions().with_entities(column).distinct() if value is not None}


def get_filter_domains() -> dict:
    return {attribute: _distinct(getattr(PracticeSession, column))
            for _, attribute, column in _FIELDS
            if attribute in ("seasons", "activities", "workout_types", "location_ids")}


def _values(value):
    return value if isinstance(value, (list, tuple, set)) else [value]


def parse_filters(args: MultiDict, dashboard: Dashboard, domains=None) -> Filters:
    domains = {**(get_filter_domains() if domains is None else domains), "days": set(DAYS),
               "formats": set(FORMATS), "kinds": set(KINDS), "categories": set(CATEGORIES)}
    result = Filters()
    for name, attribute, _ in _FIELDS:
        def valid(values, *, fixed=False):
            # Fixed data constraints must survive an empty/missing DB domain.
            # Catalog constraints still reject invalid dashboard configuration.
            check_domain = not fixed or attribute in ("days", "formats", "kinds", "categories")
            cleaned = []
            for value in values:
                if attribute == "location_ids":
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        continue
                if (not check_domain or value in domains.get(attribute, set())) and value not in cleaned:
                    cleaned.append(value)
            return cleaned

        values = valid(args.getlist(name)) if name in dashboard.filters else []
        if not values:
            values = valid(_values(dashboard.defaults.get(attribute, dashboard.defaults.get(name, []))))
        if attribute in dashboard.fixed or name in dashboard.fixed:
            values = valid(_values(dashboard.fixed.get(attribute, dashboard.fixed.get(name))), fixed=True)
        setattr(result, attribute, values)

    for attribute in ("date_from", "date_to"):
        def iso(value):
            if isinstance(value, date):
                return value
            try:
                # HTML date inputs and shared URLs use the extended ISO form.
                return date.fromisoformat(value) if len(value) == 10 else None
            except (TypeError, ValueError):
                return None
        value = iso(args.get(attribute, "")) if "date_range" in dashboard.filters else None
        if value is None:
            value = iso(dashboard.defaults.get(attribute, ""))
        if attribute in dashboard.fixed:
            value = iso(dashboard.fixed[attribute])
        setattr(result, attribute, value)
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
    domains = get_filter_domains() if domains is None else domains
    locations = _past_sessions().with_entities(
        PracticeSession.location_id, PracticeSession.location_name).filter(
        PracticeSession.location_id.isnot(None)).distinct().all()
    days = _distinct(PracticeSession.day_of_week)
    formats = _distinct(PracticeSession.format)
    kinds = _distinct(PracticeSession.kind)
    # Same-year fall/winter comes after spring/summer; labels begin with the year.
    seasons = sorted(domains["seasons"], key=lambda value: (
        value[:4], "Fall/Winter" in value, value), reverse=True)
    return {"seasons": seasons, "activities": sorted(domains["activities"]),
            "workout_types": sorted(domains["workout_types"]),
            "locations": sorted({(id_, name or f"Location {id_}") for id_, name in locations}, key=lambda item: (item[1], item[0])),
            "days": [value for value in DAYS if value in days],
            "formats": [value for value in FORMATS if value in formats],
            "kinds": [value for value in KINDS if value in kinds],
            "categories": [c for c in CATEGORIES if c in _distinct(PracticeSession.category)]}


def footer() -> dict:
    latest = db.session.query(func.max(SlackArchiveMessage.synced_at)).scalar()
    return {"data_through": utils.format_datetime_central(latest) if latest else None,
            "needs_review": PracticeSession.query.filter_by(needs_review=True).count()}
