"""Append-only log of reaction adds/removals on archived channels.

The only record of un-checks (removed RSVPs). Must never affect attendance
handling: every failure is logged and swallowed."""
import logging

from app.analytics import CHANNELS
from app.models import db

logger = logging.getLogger(__name__)


def record_reaction_event(*, channel, message_ts, emoji, slack_uid, removed,
                          event_ts=None, commit=True):
    if channel not in CHANNELS or not (message_ts and emoji and slack_uid):
        return False
    try:
        from app.analytics.models import SlackReactionEvent
        db.session.add(SlackReactionEvent(
            channel_id=channel, message_ts=message_ts, emoji=emoji,
            slack_uid=slack_uid, action="removed" if removed else "added",
            event_ts=event_ts))
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            logger.warning("reaction event log rollback failed", exc_info=True)
        logger.warning("reaction event log failed for %s %s", channel, message_ts, exc_info=True)
        return False
