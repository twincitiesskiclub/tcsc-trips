"""One-off: simulate tomorrow's 8am scheduler job, post to a test channel,
then revert DB writes + delete logging threads it created.

Usage:
    python scripts/test_post_tomorrow_8am.py <CHANNEL_ID> [YYYY-MM-DD]

If date omitted, defaults to tomorrow (Central).
"""
import os
import sys
from datetime import datetime as real_datetime, timedelta, date as real_date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

PROD_DB_URL = os.environ.get("PROD_DATABASE_URL")
if not PROD_DB_URL:
    raise SystemExit("PROD_DATABASE_URL not set — add it to .env")
os.environ['DATABASE_URL'] = PROD_DB_URL

if len(sys.argv) < 2:
    print("usage: test_post_tomorrow_8am.py <CHANNEL_ID> [YYYY-MM-DD]")
    sys.exit(1)

CHANNEL_ID = sys.argv[1]

central = ZoneInfo('America/Chicago')
if len(sys.argv) >= 3:
    y, m, d = map(int, sys.argv[2].split('-'))
    target_date = real_date(y, m, d)
else:
    target_date = (real_datetime.now(central) + timedelta(days=1)).date()

fake_now = real_datetime(target_date.year, target_date.month, target_date.day, 8, 0, 0, tzinfo=central)
print(f"Simulating run_practice_announcements_job at {fake_now.isoformat()} (Central)")
print(f"Test channel: {CHANNEL_ID}")
print(f"Looking for practices on {target_date.isoformat()} (evening window: 12:00-23:59)")
print("=" * 70)

# Monkeypatch datetime in scheduler module BEFORE importing/calling
import app.scheduler as scheduler_mod

class FakeDatetime(real_datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return fake_now.astimezone(tz)
        return fake_now.replace(tzinfo=None)
    @classmethod
    def utcnow(cls):
        return fake_now.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

scheduler_mod.datetime = FakeDatetime

from app import create_app
from app.practices.models import Practice
from app.models import db

# Patch channel lookup so we can pass a raw channel ID through channel_override.
# The override path calls get_channel_id_by_name(...) which expects a name.
import app.slack.practices.announcements as _ann_mod
_orig_get_channel_id_by_name = _ann_mod.get_channel_id_by_name
def _patched_get_channel_id_by_name(name):
    if name == CHANNEL_ID or name.lstrip('#') == CHANNEL_ID:
        return CHANNEL_ID
    return _orig_get_channel_id_by_name(name)
_ann_mod.get_channel_id_by_name = _patched_get_channel_id_by_name

app = create_app()

with app.app_context():
    # Snapshot tomorrow's practices BEFORE running
    today_start_naive = real_datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    today_end_naive = today_start_naive + timedelta(days=1)
    candidates = Practice.query.filter(
        Practice.date >= today_start_naive,
        Practice.date < today_end_naive,
    ).order_by(Practice.date).all()

    print(f"\nFound {len(candidates)} practice(s) on {target_date.isoformat()}:")
    snapshot = {}
    for p in candidates:
        snapshot[p.id] = {
            'slack_message_ts': p.slack_message_ts,
            'slack_channel_id': p.slack_channel_id,
            'slack_log_message_ts': p.slack_log_message_ts,
        }
        types = ', '.join([t.name for t in p.practice_types]) if p.practice_types else 'no-type'
        loc = p.location.name if p.location else 'no-location'
        print(f"  #{p.id}  {p.date.strftime('%a %I:%M %p')}  {types}  @ {loc}  "
              f"(msg_ts={p.slack_message_ts}, log_ts={p.slack_log_message_ts})")

print("\n" + "=" * 70)
print("Calling run_practice_announcements_job(...)")
print("=" * 70)

# Run the actual job
scheduler_mod.run_practice_announcements_job(app, channel_override=CHANNEL_ID)

print("\n" + "=" * 70)
print("CLEANUP: reverting DB writes + deleting any logging threads created")
print("=" * 70)

from app.slack.client import get_slack_client
from app.slack.practices._config import LOGGING_CHANNEL_ID

client = get_slack_client()

with app.app_context():
    # Re-fetch the same practices
    candidates_after = Practice.query.filter(Practice.id.in_(list(snapshot.keys()))).all()
    affected = []
    for p in candidates_after:
        before = snapshot[p.id]
        new_msg_ts = p.slack_message_ts if p.slack_message_ts != before['slack_message_ts'] else None
        new_log_ts = p.slack_log_message_ts if p.slack_log_message_ts != before['slack_log_message_ts'] else None
        if new_msg_ts or new_log_ts:
            affected.append({
                'practice': p,
                'new_msg_ts': new_msg_ts,
                'new_log_ts': new_log_ts,
                'new_channel_id': p.slack_channel_id,
            })

    print(f"\n{len(affected)} practice(s) had DB changes; reverting…")

    deleted_log_threads = set()
    for a in affected:
        p = a['practice']
        if a['new_log_ts'] and a['new_log_ts'] not in deleted_log_threads:
            try:
                client.chat_delete(channel=LOGGING_CHANNEL_ID, ts=a['new_log_ts'])
                print(f"  deleted #tcsc-logging thread ts={a['new_log_ts']} (practice #{p.id})")
                deleted_log_threads.add(a['new_log_ts'])
            except Exception as e:
                print(f"  WARN: could not delete log thread {a['new_log_ts']}: {e}")

        # Restore original snapshot
        before = snapshot[p.id]
        p.slack_message_ts = before['slack_message_ts']
        p.slack_channel_id = before['slack_channel_id']
        p.slack_log_message_ts = before['slack_log_message_ts']
        print(f"  reverted practice #{p.id} DB fields to pre-test state")

    db.session.commit()

print("\n" + "=" * 70)
print("DONE. The Slack post(s) in the test channel remain for review.")
print(f"Test channel: {CHANNEL_ID}")
print("Logging threads (if any) were deleted. Practice rows restored to original state.")
print("Tomorrow's 8am scheduler job will run as if this test never happened.")
