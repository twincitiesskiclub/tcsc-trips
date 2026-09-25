"""Trip sign-ups from Slack Workflow posts, and trip sessions. Pure."""
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

from app.analytics.drafts import AttendanceDraft, SessionDraft, TripSignup
from app.analytics.seasons import season_label

_CENTRAL = ZoneInfo("America/Chicago")
HEADER = re.compile(r"submitted\.\s+this does not mean that they have paid", re.I)
_MENTION = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>")
_ANSWER = re.compile(r"\*What's your (first name|last name|name)\?\*\n([^\n]*)", re.I)


def normalize_name(text: str) -> str:
    return " ".join(text.lower().split())


def edition_year(day: date) -> int:
    return day.year if day.month >= 6 else day.year - 1


def is_signup_post(raw: dict) -> bool:
    return raw.get("subtype") == "bot_message" and bool(HEADER.search(raw.get("text", "")))


def _series(username: str, cfg) -> str | None:
    text = username.lower()
    return next((rule["slug"] for rule in cfg.trip_series
                 if any(match.lower() in text for match in rule["match"])), None)


def parse_signup(message, cfg) -> TripSignup | None:
    raw = message.raw
    if not is_signup_post(raw):
        return None
    slug = _series(raw.get("username", ""), cfg)
    if slug is None:
        return None
    posted_on = datetime.fromtimestamp(float(message.ts), _CENTRAL).date()
    body = raw["text"].split("\n", 1)[1] if "\n" in raw["text"] else ""
    answers = {label.lower(): value.strip() for label, value in _ANSWER.findall(body)}
    if "first name" in answers:
        name = f"{answers['first name']} {answers.get('last name', '')}".strip()
    elif "name" in answers:
        name = answers["name"]
    else:
        name = next((line.strip() for line in body.splitlines()
                     if line.strip() and not line.strip().startswith(("<", "*"))), "")
    mentions = list(dict.fromkeys(_MENTION.findall(body)))
    # Typed names win: one member often signs up another. A lone mention is a fallback.
    uid = mentions[0] if len(mentions) == 1 else None
    if not name and not uid:
        return None
    return TripSignup(slug, edition_year(posted_on), posted_on, uid, name or None,
                      f"{message.channel_id}:{message.ts}")


def trip_sessions(signups, corrections, seasons):
    """One session per series edition; one signup row per distinct person."""
    editions = {}
    for signup in signups:
        editions.setdefault((signup.series_slug, signup.edition_year), []).append(signup)
    sessions, attendance = [], []
    for (slug, year), group in sorted(editions.items()):
        key = f"trip:{slug}:{year}"
        fields = corrections.get(key, {})
        if fields.get("skip"):
            continue
        dated = "date" in fields
        day = date.fromisoformat(fields["date"]) if dated else max(s.posted_on for s in group)
        people = {}
        for signup in sorted(group, key=lambda s: s.source_key):
            name = normalize_name(signup.person_name) if signup.person_name else None
            if signup.user_id is not None:
                person = f"slack:{signup.slack_uid}" if signup.slack_uid else f"user:{signup.user_id}"
            else:
                person = f"name:{name}" if name else f"slack:{signup.slack_uid}"
            source = "app" if signup.source_key.startswith("trip_registration:") else "post_text"
            people.setdefault(person, AttendanceDraft(key, signup.slack_uid, "signup", None, None,
                                                      source, name, signup.user_id))
        flags = [] if dated else ["missing_date"]
        sessions.append(SessionDraft(
            session_key=key, group_key=key, era="trip", date=day, start_time=None,
            title=fields.get("title") or f"{slug.replace('-', ' ').title()} ({year} Fall/Winter)",
            kind="trip", category="trip", status=fields.get("status", "held"),
            flags=flags, needs_review=not dated, rsvp_count=len(people),
            day_of_week=day.strftime("%A"), season_label=season_label(day, seasons),
            lat=None, lon=None,
        ))
        attendance.extend(people.values())
    return sessions, attendance
