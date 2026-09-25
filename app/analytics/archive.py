"""Layer 1: copy Slack channels into slack_archive_messages.

Callers commit. Functions take a slack_sdk-like client so tests can pass a
fake; production passes get_slack_client() (bot) or get_slack_user_client()
(user token, needed only for the archived #announcements-summer)."""
import logging
from datetime import datetime, timedelta, timezone
from time import time

from sqlalchemy.dialects.postgresql import insert

from app.analytics import SYNC_CHANNELS
from app.analytics.models import SlackArchiveMessage
from app.models import db

logger = logging.getLogger(__name__)


def _utc(ts):
    return datetime.fromtimestamp(float(ts), timezone.utc).replace(tzinfo=None)


def upsert_message(channel_id: str, raw: dict) -> SlackArchiveMessage:
    """Insert or refresh the complete snapshot without committing."""
    edited = raw.get("edited") or {}
    values = dict(
        channel_id=channel_id, ts=raw["ts"], thread_ts=raw.get("thread_ts"),
        user_id=raw.get("user"), bot_id=raw.get("bot_id"), subtype=raw.get("subtype"),
        text=raw.get("text") or "", posted_at=_utc(raw["ts"]),
        edited_at=_utc(edited["ts"]) if edited.get("ts") else None,
        deleted_at=None, raw=raw, synced_at=_utc(time()))
    stmt = insert(SlackArchiveMessage).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_slack_archive_channel_ts",
        set_={k: stmt.excluded[k] for k in values if k not in ("channel_id", "ts")})
    return db.session.scalars(
        stmt.returning(SlackArchiveMessage),
        execution_options={"populate_existing": True},
    ).one()


def _complete_reactions(client, channel_id, raw):
    """conversations.history caps each reaction's users list; refetch when short."""
    reactions = raw.get("reactions") or []
    if not any(r.get("count", 0) > len(r.get("users", [])) for r in reactions):
        return raw, False
    resp = client.reactions_get(channel=channel_id, timestamp=raw["ts"], full=True)
    full = (resp.get("message") or {}).get("reactions") or reactions
    return {**raw, "reactions": full}, True


def _paginate(call, key="messages", **kwargs):
    cursor = None
    while True:
        resp = call(cursor=cursor, limit=200, **kwargs)
        yield from resp.get(key) or []
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return


def import_channel(client, channel_id: str, *, oldest: float | None = None) -> dict:
    """Import history and every returned parent's thread, following cursors."""
    stats = {"messages": 0, "replies": 0, "reactions_refetched": 0, "seen": set()}
    kwargs = {"channel": channel_id}
    if oldest is not None:
        kwargs["oldest"] = str(oldest)
        kwargs["inclusive"] = True
    for raw in _paginate(client.conversations_history, **kwargs):
        raw, refetched = _complete_reactions(client, channel_id, raw)
        upsert_message(channel_id, raw)
        stats["messages"] += 1
        stats["reactions_refetched"] += refetched
        stats["seen"].add(raw["ts"])
        if raw.get("reply_count"):
            for reply in _paginate(client.conversations_replies, channel=channel_id, ts=raw["ts"]):
                if reply["ts"] == raw["ts"]:
                    continue
                reply, refetched = _complete_reactions(client, channel_id, reply)
                upsert_message(channel_id, reply)
                stats["replies"] += 1
                stats["reactions_refetched"] += refetched
                stats["seen"].add(reply["ts"])
    return stats


def sync_recent(
    client, channel_ids=SYNC_CHANNELS, *, days: int = 21, now: datetime | None = None
) -> dict:
    """Refresh the recent window and mark observable missing rows deleted."""
    now = now or _utc(time())
    since = now - timedelta(days=days)
    out = {}
    for channel_id in channel_ids:
        try:
            with db.session.begin_nested():
                stats = import_channel(client, channel_id,
                                       oldest=(since - datetime(1970, 1, 1)).total_seconds())
                # Anything archived in the window that Slack no longer returns was deleted.
                # Only top-level messages and replies of threads we re-fetched are judged.
                stale = SlackArchiveMessage.query.filter(
                    SlackArchiveMessage.channel_id == channel_id,
                    SlackArchiveMessage.posted_at >= since,
                    SlackArchiveMessage.deleted_at.is_(None),
                    ~SlackArchiveMessage.ts.in_(stats["seen"] or {""}),
                ).all()
                deleted = 0
                for row in stale:
                    if row.thread_ts and row.thread_ts != row.ts and row.thread_ts not in stats["seen"]:
                        continue
                    row.deleted_at = _utc(time())
                    deleted += 1
                stats["deleted"] = deleted
        except Exception as exc:
            logger.exception("analytics sync %s failed: %s", channel_id, exc)
            out[channel_id] = {"error": str(exc)}
            continue
        out[channel_id] = {k: v for k, v in stats.items() if k != "seen"}
        logger.info("analytics sync %s: %s", channel_id, out[channel_id])
    return out
