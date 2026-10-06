"""Validated per-post corrections stored in the DB. Callers own the commit."""
import json
from datetime import date
from pathlib import Path
import re

from app.analytics import CATEGORIES
from app.analytics.models import AnalyticsCorrection
from app.models import db


_POST_KEY = r"C[A-Z0-9]+:\d+\.\d+"
TRIP_KEY = re.compile(r"trip:([a-z0-9-]+):(\d{4})")
GAP_KEY_PREFIX = "gap:"
GAP_KEY = re.compile(rf"{GAP_KEY_PREFIX}(\d{{4}}-\d{{2}}-\d{{2}})")
_KEY = re.compile(rf"(?:{_POST_KEY}(?::(?:early|late|merged|main|\d{{4}}-\d{{2}}-\d{{2}}))?|practice:\d+"
                  rf"|{TRIP_KEY.pattern}|{GAP_KEY.pattern})")
_ROLES = ("rsvp", "plan", "lead", "coach", "signup", "decline")


class CorrectionError(ValueError):
    """A correction cannot safely be applied."""


def _iso_date(value):
    if not (isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _strings(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _people(value):
    return isinstance(value, list) and all(
        isinstance(entry, dict)
        and isinstance(entry.get("slack_uid"), str)
        and bool(re.fullmatch(r"[UW][A-Z0-9]{2,19}", entry["slack_uid"]))
        and entry.get("role") in _ROLES
        for entry in value)


def _emoji_roles(value):
    return isinstance(value, dict) and bool(value) and all(
        isinstance(emoji, str) and emoji.strip() and role in ("rsvp", "decline", "plan")
        for emoji, role in value.items())


_BOOL = (lambda value: isinstance(value, bool), "a bool")
_TEXT = (lambda value: isinstance(value, str) and bool(value.strip()), "a non-empty string")
_STRINGS = (_strings, "a list of strings")
_PEOPLE = (_people, "a list of {slack_uid, role}, with role rsvp/plan/lead/coach/signup/decline")
# field -> (check, what the error says was expected)
_CHECKS = {
    "create": _BOOL, "skip": _BOOL, "merged": _BOOL, "ok": _BOOL,
    "kind": (lambda value: value in ("practice", "event", "trip"), "practice or event or trip"),
    "status": (lambda value: value in ("held", "cancelled"), "held or cancelled"),
    "date": (_iso_date, "an ISO date (YYYY-MM-DD)"),
    "start_time": (lambda value: isinstance(value, str)
                   and bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value)), "HH:MM"),
    "location": (lambda value: isinstance(value, str), "a string"),
    "add": _PEOPLE, "remove": _PEOPLE,
    "title": _TEXT, "gap_ok": _TEXT,
    "category": (lambda value: value in CATEGORIES, " or ".join(CATEGORIES)),
    "reported_count": (lambda value: type(value) is int and value >= 0, "a non-negative integer"),
    "emoji_roles": (_emoji_roles, "a non-empty {emoji: rsvp|decline|plan} mapping"),
    "rsvp_emoji": _STRINGS, "plan_emoji": _STRINGS, "activities": _STRINGS, "types": _STRINGS,
    "rsvp_from": (lambda value: _strings(value) and all(re.fullmatch(_POST_KEY, item) for item in value),
                  "a list of channel:ts references"),
}
CORRECTION_FIELDS = set(_CHECKS)


def validate_correction(key: str, fields: dict) -> dict:
    """Validate a key and its fields without changing either."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise CorrectionError("key: expected channel:ts[:slot], practice:id, trip:slug:YYYY or gap:YYYY-MM-DD")
    if not isinstance(fields, dict) or not fields:
        raise CorrectionError("fields: expected a non-empty mapping")
    for field, value in fields.items():
        if field not in _CHECKS:
            raise CorrectionError(f"{field}: unknown correction field")
        check, expected = _CHECKS[field]
        if not check(value):
            raise CorrectionError(f"{field}: expected {expected}")
    gap = GAP_KEY.fullmatch(key)
    if gap:
        if set(fields) != {"gap_ok"}:
            raise CorrectionError("gap keys take only gap_ok")
        try:
            gap_date = date.fromisoformat(gap[1])
        except ValueError as exc:
            raise CorrectionError("gap key: expected a valid ISO date") from exc
        if gap_date.weekday() != 0:
            raise CorrectionError("gap key: expected a Monday")
    elif "gap_ok" in fields:
        raise CorrectionError("gap_ok: only on gap:YYYY-MM-DD keys")
    if "create" in fields and not re.fullmatch(_POST_KEY, key):
        raise CorrectionError("create: expected a post key (channel:ts without a slot)")
    if fields.get("create") and "date" not in fields:
        raise CorrectionError("date: required when create is true")
    return fields


def _validate_entry(key, fields, note, author):
    validate_correction(key, fields)
    if not isinstance(note, str) or not note.strip():
        raise CorrectionError(f"{key}: note must be a non-empty string")
    if not isinstance(author, str) or not author.strip():
        raise CorrectionError(f"{key}: author must be a non-empty string")


def load_corrections() -> dict[str, dict]:
    return {row.key: row.fields for row in AnalyticsCorrection.query.order_by(AnalyticsCorrection.key).all()}


def upsert_correction(key, fields, note, author) -> AnalyticsCorrection:
    """Insert or replace a correction, leaving the transaction to the caller."""
    _validate_entry(key, fields, note, author)
    row = AnalyticsCorrection.query.filter_by(key=key).one_or_none()
    if row is None:
        row = AnalyticsCorrection(key=key)
        db.session.add(row)
    row.fields = fields
    row.note = note
    row.author = author
    return row


def import_corrections(path) -> int:
    """Validate the whole JSON document before adding or changing any row."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise CorrectionError(f"corrections file: {exc}") from exc
    if not isinstance(data, dict):
        raise CorrectionError("corrections file: expected a mapping")
    entries = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            raise CorrectionError(f"{key}: expected a mapping with fields and note")
        values = (key, entry.get("fields"), entry.get("note"), entry.get("author", "claude-fixer"))
        _validate_entry(*values)
        entries.append(values)
    for values in entries:
        upsert_correction(*values)
    return len(entries)


def export_corrections(path) -> int:
    data = {row.key: {"fields": row.fields, "note": row.note, "author": row.author}
            for row in AnalyticsCorrection.query.order_by(AnalyticsCorrection.key).all()}
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(data)
