"""Completeness checks over the archive and the lineage. Pure functions."""
import re

from app.analytics import CANDIDATE_CHANNELS
from app.analytics.history_config import base_emoji
from app.analytics.parse_template import is_weekly_preview

RSVP_PHRASE = re.compile(
    r"\b(hit|bop|smash|react(?:ing)?\s+with|give\s+(?:it\s+)?an?|rsvp)\b[^\n]{0,60}?"
    r":([a-z0-9_+'-]+(?:::skin-tone-\d)?):", re.I)
_SYSTEM_SUBTYPES = {"channel_join", "channel_leave", "channel_purpose", "channel_topic",
                    "channel_name", "channel_archive", "channel_unarchive", "bot_add",
                    "bot_remove", "pinned_item", "tombstone"}


def is_candidate(raw: dict, applause: frozenset) -> bool:
    """RSVP wording that names an emoji, or 5+ of one non-applause reaction."""
    if RSVP_PHRASE.search(raw.get("text", "")):
        return True
    return any(reaction.get("count", 0) >= 5 and base_emoji(reaction["name"]) not in applause
               for reaction in raw.get("reactions", []))


def _resolved_posts(corrections: dict) -> set[str]:
    resolved = set()
    for key, fields in corrections.items():
        if key.startswith("C"):
            resolved.add(":".join(key.split(":")[:2]))
        resolved.update(fields.get("rsvp_from", []))
    return resolved


def find_candidates(messages, produced_posts, corrections, applause) -> list[str]:
    """Top-level posts that look like attendance but produced no session and have no correction."""
    resolved = _resolved_posts(corrections)
    found = []
    for message in messages:
        raw = message.raw
        key = f"{message.channel_id}:{message.ts}"
        if (message.channel_id not in CANDIDATE_CHANNELS or message.deleted
                or raw.get("thread_ts", message.ts) != message.ts
                or raw.get("subtype") in _SYSTEM_SUBTYPES
                or (message.channel_id, message.ts) in produced_posts or key in resolved
                or is_weekly_preview(raw.get("text", ""))):
            continue
        if is_candidate(raw, applause):
            found.append(key)
    return sorted(found)
