"""Pure extraction of app-era sessions from practice rows and archived posts."""
from collections import defaultdict
from html import unescape
import re

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef, SessionDraft
from app.analytics.history_config import (
    HistoryConfig, activity_bucket, resolve_venue, workout_bucket,
)
from app.analytics.parse_template import parse_times


_EMOJI = re.compile(r":([\w+\-]+):")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_WEEKDAY = re.compile(
    r"\b(" + "|".join(day[:3] + "(?:" + day[3:] + ")?" for day in _WEEKDAYS) + r")\b",
    re.IGNORECASE,
)


def parse_rsvp_mapping(blocks_text: str) -> dict[str, str]:
    """Read labeled RSVP emoji or lift clock pairs, preserving their labels."""
    mapping = {}
    for line in unescape(blocks_text).replace("*", "").splitlines():
        instruction = re.search(r"\bRSVP\s*:\s*", line, re.IGNORECASE)
        if instruction:
            line = line[instruction.end():]
        emojis = list(_EMOJI.finditer(line))
        for index, emoji in enumerate(emojis):
            end = emojis[index + 1].start() if index + 1 < len(emojis) else len(line)
            label = line[emoji.end():end].strip(" \t|&,;")
            if instruction and (_WEEKDAY.search(label) or parse_times(label)):
                mapping[emoji[1]] = label
            elif emoji[1] in ("six", "seven") and parse_times(label):
                mapping[emoji[1]] = label
    return mapping


def _text_values(value):
    """Collect text strings at any depth in Slack Block Kit payloads."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "text" and isinstance(child, str):
                yield child
            else:
                yield from _text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _text_values(child)


def _mapped_emoji(practice: AppPractice, mapping: dict[str, str]) -> str | None:
    scores = {}
    for emoji, label in mapping.items():
        weekday = _WEEKDAY.search(label)
        day_matches = bool(weekday and weekday[1][:3].lower() ==
                           _WEEKDAYS[practice.date.weekday()][:3].lower())
        time_matches = practice.date.time() in parse_times(label)
        scores[emoji] = int(day_matches) + int(time_matches)
    best = max(scores.values(), default=0)
    candidates = [emoji for emoji, score in scores.items() if score == best]
    return candidates[0] if best and len(candidates) == 1 else None


def _venue(practice: AppPractice, cfg: HistoryConfig, locations: list[LocationRef]) -> dict:
    location = next((loc for loc in locations if loc.name == practice.location_name
                     and loc.spot == practice.location_spot), None)
    if location is None:
        return resolve_venue(f"{practice.location_name} - {practice.location_spot}", cfg, locations)
    indoor = {name.lower().replace("’", "'") for name in cfg.indoor_locations}
    return {
        "location_id": location.id, "location_name": location.name,
        "lat": location.lat if location.lat is not None else cfg.default_lat,
        "lon": location.lon if location.lon is not None else cfg.default_lon,
        "is_indoor": any(value.lower().replace("’", "'") in indoor
                         for value in (location.name, location.spot) if value),
        "matched": True, "rule_kind": "location",
    }


def extract_app_sessions(
    practices: list[AppPractice],
    messages_by_ts: dict[tuple[str, str], ArchivedMessage],
    cfg: HistoryConfig,
    locations: list[LocationRef],
) -> list[SessionDraft]:
    """Build one session per posted, non-draft practice without I/O or mutation."""
    groups = defaultdict(list)
    for practice in practices:
        if not practice.is_draft and practice.slack_message_ts:
            groups[(practice.slack_channel_id, practice.slack_message_ts)].append(practice)

    sessions = []
    for (channel, ts), group in groups.items():
        group = sorted(group, key=lambda practice: practice.date)
        message = messages_by_ts.get((channel, ts))
        mapping = parse_rsvp_mapping("\n".join(_text_values({
            "text": message.raw.get("text", ""), "blocks": message.raw.get("blocks", []),
        }))) if message is not None else {}
        split = len(group) == 2 and group[0].date.date() == group[1].date.date()
        for index, practice in enumerate(group):
            flags = [] if message is not None else ["post_missing"]
            slot = ("early" if index == 0 else "late") if split else None
            emoji = practice.slack_session_emoji
            if not emoji:
                if len(group) == 1:
                    emoji = "white_check_mark"
                else:
                    emoji = _mapped_emoji(practice, mapping)
                    if (emoji is None and split and practice.date.weekday() == 3
                            and "Strength" in practice.activities):
                        emoji = "six" if slot == "early" else "seven"
                    if emoji is None:
                        flags.append("emoji_unknown")

            venue = _venue(practice, cfg, locations)
            if not venue["matched"]:
                flags.append("unknown_venue")
            if venue["rule_kind"] == "location" and venue["location_id"] is None:
                flags.append("unknown_location_row")
            title = (", ".join(practice.activities) + " - " + ", ".join(practice.types)
                     if practice.activities or practice.types else "Practice")
            sessions.append(SessionDraft(
                session_key=f"practice:{practice.id}", group_key=f"{channel}:{ts}", era="app",
                date=practice.date.date(), start_time=practice.date.time(), title=title,
                venue_raw=f"{practice.location_name} - {practice.location_spot}",
                location_id=venue["location_id"], location_name=venue["location_name"],
                lat=venue["lat"], lon=venue["lon"], is_indoor=venue["is_indoor"],
                activities=list(practice.activities), workout_types=list(practice.types),
                activity=activity_bucket(practice.activities, cfg),
                workout_type=workout_bucket(practice.types, cfg),
                kind="event" if "Kickoff" in practice.activities else "practice",
                format="split" if split else "single", slot=slot, rsvp_emoji=emoji,
                status="cancelled" if practice.status == "cancelled" else "held",
                channel_id=channel, source_ts=ts,
                source_archive_id=message.archive_id if message is not None else None,
                practice_id=practice.id, lead_uids=list(practice.lead_uids),
                coach_uids=list(practice.coach_uids), plan_emoji=list(practice.plan_emoji), flags=flags,
            ))
    return sessions
