"""Combine archived posts and app practices into a pure, normalized lineage."""
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from html import unescape
import re
from zoneinfo import ZoneInfo

from app.analytics import SESSION_CHANNELS
from app.analytics.drafts import (
    AppPractice, ArchivedMessage, AttendanceDraft, LineageResult, LocationRef,
    SeasonRef, SessionDraft,
)
from app.analytics.history_config import (
    HistoryConfig, activity_bucket, base_emoji, classify_title, resolve_venue, workout_bucket,
)
from app.analytics.parse_app import extract_app_sessions
from app.analytics.parse_template import (
    extract_template_sessions, is_weekly_preview, looks_like_template,
)
from app.analytics.seasons import season_label


MERGE_RE = re.compile(r"\b(combin\w*|merg\w*|one session|single session|one lift)\b", re.I)
CANCEL_RE = re.compile(r"\bcancel(l?ed|l?ing|s)?\b", re.I)
_CENTRAL = ZoneInfo("America/Chicago")
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?!\d)\s*(AM|PM)?", re.I)
_MISS_EMOJI = {"white_check_mark", "six", "seven", "zap", "meow-coffee", "ballot_box_with_check"}


@dataclass
class _Session:
    """Builder-only provenance, including intent that survives a merge."""
    draft: SessionDraft
    emoji_slots: dict
    button_slots: list[tuple[str, str | None]] = field(default_factory=list)
    correction_keys: list = field(default_factory=list)
    rsvp_from: list = field(default_factory=list)


def _top_level(message):
    return message.raw.get("thread_ts", message.ts) == message.ts


def _reply_date(reply):
    return datetime.fromtimestamp(float(reply["ts"]), _CENTRAL).date()


def _merge_time(text):
    match = _CLOCK.search(text)
    if match:
        hour, minute = int(match[1]), int(match[2])
        if 1 <= hour <= 12 and minute < 60:
            return time(hour % 12 + (0 if (match[3] or "PM").upper() == "AM" else 12), minute)
        if not match[3] and 0 <= hour <= 23 and minute < 60:
            return time(hour, minute)
    return None


def _created_draft(message, fields, cfg, locations):
    line = next((line for line in message.raw.get("text", "").splitlines() if line.strip()), "")
    title = unescape(line).replace("*", "").replace("_", "").strip()[:120]
    classification = classify_title(title, cfg)
    venue = resolve_venue(fields.get("location"), cfg, locations)
    activities = list(fields.get("activities", classification["activities"]))
    types = list(fields.get("types", classification["workout_types"]))
    emojis = list(fields.get("rsvp_emoji", ["white_check_mark"]))
    key = f"{message.channel_id}:{message.ts}"
    return SessionDraft(
        session_key=f"{key}:main", group_key=key, era="template",
        date=date.fromisoformat(fields["date"]),
        start_time=time.fromisoformat(fields["start_time"]) if "start_time" in fields else None,
        title=title, venue_raw=fields.get("location"),
        location_id=venue["location_id"], location_name=venue["location_name"],
        lat=venue["lat"], lon=venue["lon"], is_indoor=venue["is_indoor"],
        activities=activities, workout_types=types,
        activity=activity_bucket(activities, cfg), workout_type=workout_bucket(types, cfg),
        kind=fields.get("kind", classification["kind"]), status=fields.get("status", "held"),
        rsvp_emoji=emojis[0] if len(emojis) == 1 else None, rsvp_emoji_set=emojis,
        channel_id=message.channel_id, source_ts=message.ts, source_archive_id=message.archive_id,
    )


def _apply_fields(state, fields, cfg, locations):
    session = state.draft
    for name in ("kind", "status"):
        if name in fields:
            setattr(session, name, fields[name])
    if "date" in fields:
        value = fields["date"]
        session.date = date.fromisoformat(value) if isinstance(value, str) else value
    if "start_time" in fields:
        value = fields["start_time"]
        session.start_time = time.fromisoformat(value) if isinstance(value, str) else value
    if "location" in fields:
        session.venue_raw = fields["location"]
        venue = resolve_venue(session.venue_raw, cfg, locations)
        for name in ("location_id", "location_name", "lat", "lon", "is_indoor"):
            setattr(session, name, venue[name])
    if "activities" in fields:
        session.activities = list(fields["activities"])
        session.activity = activity_bucket(session.activities, cfg)
    if "types" in fields:
        session.workout_types = list(fields["types"])
        session.workout_type = workout_bucket(session.workout_types, cfg)
    if "rsvp_emoji" in fields:
        previous_slots = state.emoji_slots
        state.emoji_slots = {base_emoji(emoji): previous_slots.get(base_emoji(emoji), session.slot)
                             for emoji in fields["rsvp_emoji"]}
        session.rsvp_emoji = (fields["rsvp_emoji"][0]
                              if len(fields["rsvp_emoji"]) == 1 and session.format != "merged" else None)
    if "plan_emoji" in fields:
        session.plan_emoji = list(fields["plan_emoji"])
    state.rsvp_from.extend(fields.get("rsvp_from", []))


def _merge_group(group, replies, corrections, cfg, locations):
    if len(group) < 2 or any(state.draft.format != "split" for state in group):
        return group
    group = sorted(group, key=lambda state: (state.draft.start_time or time.min, state.draft.session_key))
    first = group[0].draft
    if len({state.draft.date for state in group}) != 1:
        return group
    merged_key = f"{first.group_key}:merged" if first.era == "template" else first.session_key
    keys = list(dict.fromkeys(key for state in group for key in state.correction_keys))
    if merged_key in corrections and merged_key not in keys:
        keys.append(merged_key)
    decisions = [corrections[key]["merged"] for key in keys if "merged" in corrections[key]]
    matching = next((reply for reply in replies if _reply_date(reply) == first.date
                     and MERGE_RE.search(reply.get("text", ""))), None)
    if False in decisions or not (True in decisions or (not decisions and matching)):
        return group
    if any(corrections[key].get("skip") for key in keys):
        return []
    session = replace(first, session_key=merged_key, format="merged", slot=None, rsvp_emoji=None,
                      flags=list(dict.fromkeys(flag for state in group for flag in state.draft.flags)),
                      lead_uids=list(dict.fromkeys(uid for state in group for uid in state.draft.lead_uids)),
                      coach_uids=list(dict.fromkeys(uid for state in group for uid in state.draft.coach_uids)),
                      plan_emoji=list(dict.fromkeys(emoji for state in group for emoji in state.draft.plan_emoji)))
    if matching:
        session.start_time = _merge_time(matching.get("text", "")) or session.start_time
    if not decisions:
        session.flags.append("merge_detected")
    state = _Session(session, {emoji: slot for item in group for emoji, slot in item.emoji_slots.items()},
                     [entry for item in group for entry in item.button_slots], keys,
                     [key for item in group for key in item.rsvp_from])
    # Post and early-session explicit times take precedence over reply inference.
    for key in group[0].correction_keys:
        if "start_time" in corrections[key]:
            _apply_fields(state, {"start_time": corrections[key]["start_time"]}, cfg, locations)
    # App merges retain the early key, whose fields already applied before merging.
    if first.era == "template" and merged_key in corrections:
        _apply_fields(state, corrections[merged_key], cfg, locations)
    return [state]


def _attendance(state, messages, cfg, corrections):
    session = state.draft
    rows = {}

    def add(uid, role, emoji=None, slot=None, source="correction"):
        if uid not in cfg.excluded_slack_uids:
            # Null-emoji button rows may carry both pre-merge slots. Keep the
            # persisted uniqueness of non-null reaction/correction emoji rows.
            key = (session.session_key, uid, role, emoji, slot if emoji is None else None)
            rows.setdefault(key, AttendanceDraft(session.session_key, uid, role, emoji, slot, source))

    sources = [(session.channel_id, session.source_ts)]
    sources.extend(tuple(key.split(":", 1)) for key in state.rsvp_from)
    coach_emoji = {base_emoji(emoji) for emoji in cfg.coach_emoji}
    plan_emoji = {base_emoji(emoji) for emoji in session.plan_emoji}
    for source_key in dict.fromkeys(sources):
        message = messages.get(source_key)
        if message is None:
            continue
        for reaction in message.raw.get("reactions", []):
            emoji = reaction["name"]
            base = base_emoji(emoji)
            for uid in reaction.get("users", []):
                if base in state.emoji_slots:
                    add(uid, "rsvp", emoji, state.emoji_slots[base], "reaction")
                if base in coach_emoji:
                    add(uid, "coach", emoji, source="reaction")
                if base in plan_emoji:
                    add(uid, "plan", emoji, source="reaction")
    reactors = {(row.slack_uid, row.slot) for row in rows.values() if row.role == "rsvp"}
    for uid, slot in state.button_slots:
        if (uid, slot) not in reactors:
            add(uid, "rsvp", slot=slot, source="button")
    source = "post_text" if session.era == "template" else "app"
    for role, uids in (("lead", session.lead_uids), ("coach", session.coach_uids)):
        for uid in uids:
            add(uid, role, source=source)
    for key in state.correction_keys:
        fields = corrections[key]
        for entry in fields.get("add", []):
            add(entry["slack_uid"], entry["role"], emoji=entry.get("emoji"),
                slot=entry.get("slot", session.slot if entry["role"] == "rsvp" else None))
        for entry in fields.get("remove", []):
            rows = {key: row for key, row in rows.items()
                    if (row.slack_uid, row.role) != (entry["slack_uid"], entry["role"])}
    return list(rows.values())


def build_lineage(
    messages: list[ArchivedMessage], app_practices: list[AppPractice],
    locations: list[LocationRef], seasons: list[SeasonRef], cfg: HistoryConfig,
    corrections: dict | None = None,
) -> LineageResult:
    """Build sessions and attendance without reading or writing the database."""
    corrections = corrections or {}
    indexed = {(message.channel_id, message.ts): message for message in messages if not message.deleted}
    drafts = extract_app_sessions(app_practices, indexed, cfg, locations)
    consumed = {(session.channel_id, session.source_ts) for session in drafts}
    for key, message in indexed.items():
        text = message.raw.get("text", "")
        if (message.channel_id in SESSION_CHANNELS and key not in consumed and _top_level(message)
                and not is_weekly_preview(text) and looks_like_template(text)):
            drafts.extend(extract_template_sessions(message, cfg, locations))

    produced_posts = {(session.channel_id, session.source_ts) for session in drafts}
    for key, message in indexed.items():
        fields = corrections.get(f"{message.channel_id}:{message.ts}", {})
        if (fields.get("create") is True and key not in produced_posts
                and message.channel_id in SESSION_CHANNELS and _top_level(message)):
            drafts.append(_created_draft(message, fields, cfg, locations))

    # Thread broadcasts may occur in channel history as well as in replies.
    replies = defaultdict(dict)
    for key, message in indexed.items():
        for reply in message.replies:
            if reply.get("ts") != message.ts:
                replies[key][reply["ts"]] = reply
        if not _top_level(message):
            replies[(message.channel_id, message.raw["thread_ts"])][message.ts] = message.raw
    practices = {practice.id: practice for practice in app_practices}
    groups = defaultdict(list)
    for session in drafts:
        keys = [key for key in (session.group_key, session.session_key) if key in corrections]
        if any(corrections[key].get("skip") for key in keys):
            continue
        rsvp_emojis = session.rsvp_emoji_set or ([session.rsvp_emoji] if session.rsvp_emoji else [])
        state = _Session(session, {base_emoji(emoji): session.slot for emoji in rsvp_emojis},
                         [(uid, session.slot) for uid in practices[session.practice_id].button_rsvp_uids]
                         if session.era == "app" else [], keys)
        for key in keys:
            _apply_fields(state, corrections[key], cfg, locations)
        groups[session.group_key].append(state)

    sessions, attendance = [], []
    for group in groups.values():
        first = group[0].draft
        thread = sorted(replies[(first.channel_id, first.source_ts)].values(), key=lambda reply: float(reply["ts"]))
        for state in _merge_group(group, thread, corrections, cfg, locations):
            session = state.draft
            if any(_reply_date(reply) <= session.date and CANCEL_RE.search(reply.get("text", ""))
                   for reply in thread):
                session.flags.append("cancel_language")
            rows = _attendance(state, indexed, cfg, corrections)
            session.rsvp_count = len({row.slack_uid for row in rows if row.role == "rsvp"})
            session.day_of_week = session.date.strftime("%A")
            session.season_label = season_label(session.date, seasons)
            session.needs_review = bool(session.flags) and not any(
                key in corrections for key in (session.session_key, session.group_key))
            sessions.append(session)
            attendance.extend(rows)

    produced = {(session.channel_id, session.source_ts) for session in sessions}
    # A correction resolves the post even when it skips every resulting session.
    corrected_posts = {":".join(key.split(":")[:2]) for key in corrections
                       if not key.startswith("practice:")}
    corrected_posts.update(f"{session.channel_id}:{session.source_ts}" for session in drafts
                           if session.session_key in corrections)
    misses = [f"{channel}:{ts}" for (channel, ts), message in indexed.items()
              if channel in SESSION_CHANNELS and (channel, ts) not in consumed | produced
              and f"{channel}:{ts}" not in corrected_posts
              and _top_level(message) and not is_weekly_preview(message.raw.get("text", ""))
              and any(reaction.get("count", 0) >= 5 and base_emoji(reaction["name"]) in _MISS_EMOJI
                      for reaction in message.raw.get("reactions", []))]
    sessions.sort(key=lambda session: (session.date, session.start_time or time.min, session.session_key))
    return LineageResult(sessions, attendance, sorted(misses))
