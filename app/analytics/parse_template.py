"""Pure parsing of date-headed Zapier and hand-posted practice announcements."""
from datetime import date, datetime, time, timedelta
from html import unescape
import re
from zoneinfo import ZoneInfo

from app.analytics.drafts import ArchivedMessage, LocationRef, SessionDraft
from app.analytics.history_config import (
    HistoryConfig, activity_bucket, classify_title, resolve_venue, workout_bucket,
)


_CENTRAL = ZoneInfo("America/Chicago")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")
_WEEKDAY = "|".join(_WEEKDAYS)
_MONTH = "|".join(month[:3] + "(?:" + month[3:] + ")?" for month in _MONTHS)
_HEADER = re.compile(
    rf"\b(?P<weekday>{_WEEKDAY})(?:\s*&\s*(?P<weekday2>{_WEEKDAY}))?[,\s]+"
    rf"(?:(?P<month>{_MONTH})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
    r"(?:\s*&\s*(?P<day2>\d{1,2})(?:st|nd|rd|th)?)?"
    r"(?:[,\s]+(?P<year>\d{4})\b)?"
    r"|(?P<nmonth>\d{1,2})/(?P<nday>\d{1,2})/(?P<nyear>\d{4})\b)",
    re.IGNORECASE,
)
_EMOJI = re.compile(r":([\w+\-]+):")
_TIME = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?!\d)\s*(AM|PM)?", re.IGNORECASE)
_PREVIEW = re.compile(
    r"Week of |There are \*?\d+\*? events|Weekly Practice Summary|Practices this week|"
    r"Additional details are available in the TCSC Team Calendar",
)


def _plain(text: str) -> str:
    return unescape(text).replace("*", "").replace("_", "")


def _header(text: str):
    return _HEADER.search(_plain(text[:300]))


def is_weekly_preview(text: str) -> bool:
    return bool(_PREVIEW.search(unescape(text)))


def looks_like_template(text: str) -> bool:
    plain = _plain(text)
    return _header(text) is not None and any(
        marker in plain.lower() for marker in ("bop that", "time:", "workout:", " @ ")
    )


def _valid_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_header(text: str, posted_at_central: datetime) -> tuple[list[date], list[str]]:
    """Read header dates, correcting stale or impossible dates within the post window."""
    match = _header(text)
    if match is None:
        return [], []
    posted = posted_at_central.date()
    first, last = posted - timedelta(days=1), posted + timedelta(days=8)
    month = (int(match["nmonth"]) if match["nmonth"] else
             next(i for i, name in enumerate(_MONTHS, 1)
                  if name[:3].lower() == match["month"][:3].lower()))
    year_text = match["year"] or match["nyear"]
    days = [(match["day"] or match["nday"], match["weekday"])]
    if match["day2"]:
        days.append((match["day2"], match["weekday2"]))
    dates, flags = [], []
    for day_text, weekday_text in days:
        day = int(day_text)
        weekday = _WEEKDAYS.index(weekday_text.title()) if weekday_text else None
        year = int(year_text) if year_text else posted.year
        candidate = _valid_date(year, month, day)
        if year_text is None and candidate is not None and candidate < posted - timedelta(days=30):
            candidate = _valid_date(year + 1, month, day)
        corrected = False
        if candidate is None or not first <= candidate <= last:
            corrected = True
            candidate = next((value for y in (posted.year, posted.year + 1)
                              if (value := _valid_date(y, month, day)) is not None
                              and first <= value <= last), None)
        if candidate is None or (weekday is not None and candidate.weekday() != weekday):
            corrected = True
            # An unnamed second weekday must not inherit the first day's snap.
            candidate = first
            if weekday is not None:
                candidate += timedelta(days=(weekday - first.weekday()) % 7)
        if corrected and "date_mismatch" not in flags:
            flags.append("date_mismatch")
        dates.append(candidate)
    return dates, flags


def parse_times(text: str) -> list[time]:
    """Read clock times, borrowing a following meridiem for abbreviated pairs."""
    matches = list(_TIME.finditer(_plain(text)))
    result = []
    for index, match in enumerate(matches):
        hour, minute = int(match[1]), int(match[2])
        meridiem = match[3] or next((m[3] for m in matches[index + 1:] if m[3]), None)
        if meridiem:
            if not 1 <= hour <= 12:
                continue
            hour = hour % 12 + (12 if meridiem.upper() == "PM" else 0)
        elif 1 <= hour <= 9:
            hour += 12
        if hour <= 23 and minute <= 59:
            result.append(time(hour, minute))
    return result


def parse_bop(text: str) -> list[tuple[str, str | None]]:
    """Preserve emoji names and their labels from the RSVP instruction only."""
    match = re.search(r"Bop that\b([^\n]*)", unescape(text), re.IGNORECASE)
    if match is None:
        return []
    instruction = re.split(r"so we\b|if you\b", match[1], maxsplit=1, flags=re.IGNORECASE)[0]
    emojis = list(_EMOJI.finditer(instruction))
    result = []
    for index, emoji in enumerate(emojis):
        end = emojis[index + 1].start() if index + 1 < len(emojis) else len(instruction)
        label = re.search(r"\(([^)]*)\)", instruction[emoji.end():end])
        result.append((emoji[1], label[1].replace("*", "").strip() if label else None))
    return result


def _field_values(text: str, label: str) -> list[str]:
    values = []
    pattern = re.compile(rf"^{re.escape(label.rstrip(':'))}\s*:\s*(.*)$", re.IGNORECASE)
    for line in unescape(text).splitlines():
        # Zapier decorates labels with blockquotes and emoji before the field name.
        line = re.sub(r"^\s*(?:>\s*|:[\w+\-]+:\s*)*", "", line)
        match = pattern.match(_plain(line).strip())
        if match:
            values.append(match[1].strip())
    return values


def parse_people(text: str, label: str) -> list[str]:
    return [uid for value in _field_values(text, label)
            for uid in re.findall(r"<@(U[A-Z0-9]+)(?:\|[^>]+)?>", value)]


def _title_parts(text: str) -> tuple[str, str | None]:
    lines = [line.strip() for line in _plain(text).splitlines() if line.strip()]
    for line in lines[:5]:
        # Mentions contain @ too, but are not a title/venue separator.
        at = re.search(r"(?<!<)@", line)
        if at and "details" not in line.lower():
            return line[:at.start()].strip(), line[at.end():].strip() or None
    workout = _field_values(text, "Workout")
    return (workout[0] if workout else ""), None


def parse_title(text: str) -> str:
    return _title_parts(text)[0]


def parse_venue(text: str) -> str | None:
    locations = _field_values(text, "Location")
    return (locations[0] or None) if locations else _title_parts(text)[1]


def _single_time(text: str) -> time | None:
    lines = _field_values(text, "Time")
    times = parse_times(lines[0]) if lines else []
    if not times:
        for line in text.splitlines():
            if _header(line):
                times = parse_times(line)
                break
    return times[0] if times else None


def extract_template_sessions(
    msg: ArchivedMessage, cfg: HistoryConfig, locations: list[LocationRef],
) -> list[SessionDraft]:
    """Build sessions without I/O, reactions, reply interpretation, or input mutation."""
    text = msg.raw.get("text", "")
    if is_weekly_preview(text) or not looks_like_template(text):
        return []
    posted = datetime.fromtimestamp(float(msg.raw["ts"]), _CENTRAL)
    dates, flags = parse_header(text, posted)
    if not dates:
        return []
    title, venue_raw = parse_title(text), parse_venue(text)
    venue = resolve_venue(venue_raw, cfg, locations)
    if not venue["matched"]:
        flags.append("unknown_venue")
    if venue["rule_kind"] == "location" and venue["location_id"] is None:
        flags.append("unknown_location_row")
    classification = classify_title(title, cfg)
    if not classification["matched"]:
        flags.append("unmatched_title")

    bop = parse_bop(text)
    time_lines = _field_values(text, "Time")
    times = parse_times(time_lines[0]) if time_lines else []
    combined_rsvp = (len(dates) == 1 and (len(bop) >= 3 or
                     (len(bop) == 2 and not any(parse_times(label or "") for _, label in bop))))
    if combined_rsvp:
        flags.append("emoji_ambiguous")

    def bop_time(index):
        label_times = parse_times(bop[index][1] or "")
        return label_times[0] if label_times else times[index] if index < len(times) else None

    # Each layout row holds date, time, RSVP emoji, key suffix, and optional split slot.
    if len(bop) >= 2 and len(dates) == 2:
        flags.append("multi_day")
        layout = [(day, bop_time(i), bop[i][0], day.isoformat(), None)
                  for i, day in enumerate(dates)]
    elif len(bop) == 2 and len(dates) == 1 and not combined_rsvp:
        pairs = [(bop_time(i), emoji) for i, (emoji, _) in enumerate(bop)]
        pairs.sort(key=lambda pair: (pair[0] is None, pair[0] or time.min))
        layout = [(dates[0], start, emoji, slot, slot)
                  for slot, (start, emoji) in zip(("early", "late"), pairs)]
    else:
        layout = [(dates[0], _single_time(text), bop[0][0] if bop else "white_check_mark", "main", None)]

    group_key = f"{msg.channel_id}:{msg.ts}"
    return [SessionDraft(
        session_key=f"{group_key}:{suffix}", group_key=group_key, era="template",
        date=day, start_time=start, title=title, venue_raw=venue_raw,
        location_id=venue["location_id"], location_name=venue["location_name"],
        lat=venue["lat"], lon=venue["lon"], is_indoor=venue["is_indoor"],
        activities=list(classification["activities"]), workout_types=list(classification["workout_types"]),
        activity=activity_bucket(classification["activities"], cfg),
        workout_type=workout_bucket(classification["workout_types"], cfg), kind=classification["kind"],
        format="split" if slot else "single", slot=slot, rsvp_emoji=emoji,
        rsvp_emoji_set=[emoji for emoji, _ in bop] if combined_rsvp else [],
        channel_id=msg.channel_id, source_ts=msg.ts, source_archive_id=msg.archive_id,
        lead_uids=parse_people(text, "Leads"),
        coach_uids=parse_people(text, "Coach") + parse_people(text, "Coaches"), flags=list(flags),
    ) for day, start, emoji, suffix, slot in layout]
