"""One-off cutover for lead availability v2. Run by hand at deploy.

    TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= DATABASE_URL=<prod> \
      python scripts/lead_blocks_cutover.py manual-block 2026-10-12
    ... digest-cleanup            # list what would be deleted
    ... digest-cleanup --delete   # delete it (after Rob's OK)

manual-block: creates the block's poll row as closed with no message (Chris
collected availability by hand), and posts its assignment-only block post.
digest-cleanup: finds the readiness digest posts from their summary-post
records (never by scanning the channel, where coach summaries are bot posts
too) and deletes each parent and its thread replies.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


def manual_block(start: date) -> None:
    from app.models import db
    from app.practices.availability import create_block_poll
    from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
    from app.practices.blocks import block_anchor, post_block_post
    from app.utils import now_central_naive

    end = start + timedelta(days=13)
    if start.weekday() != 0:
        print(f"refusing: {start} is not a Monday")
        sys.exit(1)
    if start >= block_anchor():
        print(f"refusing: {start} is not before the block anchor {block_anchor()}; "
              "the block job owns it")
        sys.exit(1)
    existing = LeadAvailabilityPoll.query.filter_by(starts_on=start, ends_on=end).first()
    if existing is not None and not (
            existing.status == PollStatus.CLOSED and not existing.block_post_ts):
        print(f"refusing: poll {existing.id} for {start} already exists "
              f"(status {existing.status}, block post {existing.block_post_ts})")
        sys.exit(1)

    poll = existing or create_block_poll(start, end)
    poll.status = PollStatus.CLOSED
    poll.closed_at = poll.closed_at or now_central_naive()
    db.session.commit()
    if not post_block_post(poll):
        print("POST FAILED for poll", poll.id)
        sys.exit(1)
    print("posted for poll", poll.id)


def _thread_messages(client, channel: str, ts: str) -> list[dict]:
    """Every message in the thread (parent first), following the cursor."""
    messages: list[dict] = []
    cursor = None
    while True:
        kwargs = {"channel": channel, "ts": ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.conversations_replies(**kwargs)
        messages.extend(response.get("messages", []))
        cursor = (response.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return messages


def digest_cleanup(delete: bool) -> None:
    from app.practices.models import PracticeSummaryPost
    from app.slack.client import get_slack_client
    from app.slack.practices._config import COLLAB_CHANNEL_ID
    from app.slack.practices.summary_posts import READINESS_DIGEST

    client = get_slack_client()
    records = PracticeSummaryPost.query.filter_by(surface=READINESS_DIGEST).all()
    print(f"{len(records)} readiness digest record(s)")
    for record in records:
        channel = record.channel_id or COLLAB_CHANNEL_ID
        messages = _thread_messages(client, channel, record.message_ts)
        print(f"{record.week_start} parent {record.message_ts}: "
              f"{max(len(messages) - 1, 0)} replies")
        for reply in messages[1:]:
            author = reply.get("user") or f"bot {reply.get('bot_id')}"
            snippet = (reply.get("text") or "").replace("\n", " ")[:80]
            print(f"  reply {reply['ts']} by {author}: {snippet}")
        if not delete:
            continue
        failed = False
        for reply in reversed(messages[1:]):  # replies first, parent last
            try:
                client.chat_delete(channel=channel, ts=reply["ts"])
            except Exception as exc:  # noqa: BLE001
                failed = True
                print("  could not delete reply", reply["ts"], exc)
        if failed:
            print(f"  kept parent {record.message_ts} (a reply could not be deleted)")
            continue
        try:
            client.chat_delete(channel=channel, ts=record.message_ts)
        except Exception as exc:  # noqa: BLE001
            print("  could not delete parent", record.message_ts, exc)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in ("manual-block", "digest-cleanup") or (
            command == "manual-block" and len(sys.argv) < 3):
        print(__doc__)
        sys.exit(1)
    app = create_app()
    with app.app_context():
        if command == "manual-block":
            manual_block(date.fromisoformat(sys.argv[2]))
        else:
            digest_cleanup("--delete" in sys.argv)
