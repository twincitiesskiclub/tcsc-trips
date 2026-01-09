#!/usr/bin/env python3
"""Test script for practice announcement posting.

This script posts a test practice announcement to tcsc-devs channel,
allows RSVP testing, then can clean up and post to production.

Usage:
    # Step 1: Post test to tcsc-devs
    python test_practice_post.py post-test

    # Step 2: (Manual) Test RSVP in Slack

    # Step 3: Cleanup test post and DB
    python test_practice_post.py cleanup

    # Step 4: Post to production
    python test_practice_post.py post-prod
"""

import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Load .env first to get SLACK_BOT_TOKEN etc.
load_dotenv()

# Override DATABASE_URL with production database
# Note: dpg-d4nrbauuk... (with 'a' not 'o')
PROD_DB_URL = "postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97"
os.environ['DATABASE_URL'] = PROD_DB_URL

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeRSVP
from app.practices.service import convert_practice_to_info
from app.slack.blocks import build_practice_announcement_blocks, build_combined_lift_blocks, build_coach_weekly_summary_blocks
from app.slack.client import get_slack_client
from app.slack.practices import post_practice_announcement, post_collab_review
from app.integrations.weather import get_weather_for_location

# Channel IDs
TEST_CHANNEL = "C053T1AR48Y"  # tcsc-devs
PROD_CHANNEL = "C042G463AQ1"  # announcements-practices


def get_next_unposted_practice():
    """Get the next upcoming practice that hasn't been posted yet.

    Logic: Morning practices get posted evening before, evening practices
    get posted morning of. This function simply finds the next practice
    (by datetime) that doesn't have a slack_message_ts yet.

    If multiple unposted practices exist, shows them and asks which one.
    """
    from datetime import datetime

    # Query upcoming practices that haven't been posted yet
    practices = Practice.query.filter(
        Practice.date >= datetime.now(),
        Practice.slack_message_ts.is_(None)
    ).order_by(Practice.date).all()

    if not practices:
        print("No unposted upcoming practices found")
        return None

    if len(practices) == 1:
        return practices[0]

    # Multiple practices - ask which one
    print(f"Found {len(practices)} unposted upcoming practices:")
    for i, p in enumerate(practices, 1):
        date_str = p.date.strftime('%a %b %-d')
        time_str = p.date.strftime('%I:%M %p').lstrip('0')
        loc = p.location.name if p.location else 'No location'
        print(f"  {i}. #{p.id}: {date_str} {time_str} at {loc}")

    choice = input("Which practice? (enter number): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(practices):
            return practices[idx]
    except ValueError:
        pass

    print("Invalid choice")
    return None


def get_next_posted_practice():
    """Get the next upcoming practice that HAS been posted to Slack.

    Used for updating existing announcements with new data.
    """
    from datetime import datetime

    # Query upcoming practices that have been posted
    practices = Practice.query.filter(
        Practice.date >= datetime.now(),
        Practice.slack_message_ts.isnot(None)
    ).order_by(Practice.date).all()

    if not practices:
        print("No posted upcoming practices found")
        return None

    if len(practices) == 1:
        return practices[0]

    # Multiple practices - ask which one
    print(f"Found {len(practices)} posted upcoming practices:")
    for i, p in enumerate(practices, 1):
        date_str = p.date.strftime('%a %b %-d')
        time_str = p.date.strftime('%I:%M %p').lstrip('0')
        loc = p.location.name if p.location else 'No location'
        print(f"  {i}. #{p.id}: {date_str} {time_str} at {loc}")

    choice = input("Which practice? (enter number): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(practices):
            return practices[idx]
    except ValueError:
        pass

    print("Invalid choice")
    return None


def get_next_needs_collab_practice():
    """Get the next practice that's been posted but needs collab review.

    Finds practices that have slack_message_ts (posted to announcements)
    but no slack_collab_message_ts (not yet posted to collab channel).
    """
    from datetime import datetime

    # Query upcoming practices posted but not yet sent to collab
    practices = Practice.query.filter(
        Practice.date >= datetime.now(),
        Practice.slack_message_ts.isnot(None),
        Practice.slack_collab_message_ts.is_(None)
    ).order_by(Practice.date).all()

    if not practices:
        print("No practices need collab review")
        return None

    if len(practices) == 1:
        return practices[0]

    # Multiple practices - ask which one
    print(f"Found {len(practices)} practices needing collab review:")
    for i, p in enumerate(practices, 1):
        date_str = p.date.strftime('%a %b %-d')
        time_str = p.date.strftime('%I:%M %p').lstrip('0')
        loc = p.location.name if p.location else 'No location'
        print(f"  {i}. #{p.id}: {date_str} {time_str} at {loc}")

    choice = input("Which practice? (enter number): ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(practices):
            return practices[idx]
    except ValueError:
        pass

    print("Invalid choice")
    return None


def post_test():
    """Post practice announcement to test channel."""
    app = create_app()
    with app.app_context():
        practice = get_next_unposted_practice()
        if not practice:
            return

        print(f"Found practice #{practice.id} for {practice.date}")
        print(f"  Location: {practice.location.name if practice.location else 'None'}")
        print(f"  Status: {practice.status}")

        # Convert to PracticeInfo and build blocks
        practice_info = convert_practice_to_info(practice)
        blocks = build_practice_announcement_blocks(practice_info)

        # Post to test channel
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=TEST_CHANNEL,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        print(f"\nPosted to tcsc-devs! message_ts: {message_ts}")

        # Save to practice record so RSVP testing works
        practice.slack_message_ts = message_ts
        practice.slack_channel_id = TEST_CHANNEL
        db.session.commit()
        print(f"Updated practice record with test channel info")

        # Add pre-seeded checkmark emoji for RSVP
        try:
            client.reactions_add(
                channel=TEST_CHANNEL,
                timestamp=message_ts,
                name="white_check_mark"
            )
            print("Added checkmark emoji for RSVP")
        except Exception as e:
            print(f"Could not add checkmark: {e}")

        print("\n" + "="*60)
        print("TEST POST COMPLETE")
        print("="*60)
        print(f"Message TS: {message_ts}")
        print(f"Channel: {TEST_CHANNEL}")
        print("\nNext steps:")
        print("1. Go to #tcsc-devs in Slack")
        print("2. Test RSVP by clicking the checkmark emoji")
        print("3. Run: python test_practice_post.py cleanup")
        print("4. Run: python test_practice_post.py post-prod")


def cleanup():
    """Delete test message and clear practice DB fields."""
    app = create_app()
    with app.app_context():
        practice = get_next_unposted_practice()
        if not practice:
            return

        if not practice.slack_message_ts:
            print("No slack_message_ts on practice, nothing to cleanup")
            return

        if practice.slack_channel_id != TEST_CHANNEL:
            print(f"Practice channel is {practice.slack_channel_id}, not test channel")
            print("Aborting cleanup to avoid deleting production post")
            return

        print(f"Practice #{practice.id}")
        print(f"  message_ts: {practice.slack_message_ts}")
        print(f"  channel: {practice.slack_channel_id}")

        client = get_slack_client()

        # Get thread replies to delete
        try:
            result = client.conversations_replies(
                channel=practice.slack_channel_id,
                ts=practice.slack_message_ts,
                limit=50
            )
            messages = result.get('messages', [])
            print(f"Found {len(messages)} messages in thread")

            # Delete thread replies first (skip the parent)
            for msg in messages[1:]:  # Skip first message (parent)
                try:
                    client.chat_delete(
                        channel=practice.slack_channel_id,
                        ts=msg['ts']
                    )
                    print(f"  Deleted thread reply: {msg['ts']}")
                except Exception as e:
                    print(f"  Could not delete reply {msg['ts']}: {e}")
        except Exception as e:
            print(f"Could not get thread replies: {e}")

        # Delete the main message
        try:
            client.chat_delete(
                channel=practice.slack_channel_id,
                ts=practice.slack_message_ts
            )
            print(f"Deleted main message: {practice.slack_message_ts}")
        except Exception as e:
            print(f"Could not delete main message: {e}")

        # Clear practice DB fields
        practice.slack_message_ts = None
        practice.slack_channel_id = None
        db.session.commit()
        print("Cleared practice slack fields in database")

        # Delete any test RSVPs (optional - only if you want to clean those too)
        rsvp_count = PracticeRSVP.query.filter_by(practice_id=practice.id).count()
        if rsvp_count > 0:
            print(f"\nNote: There are {rsvp_count} RSVP(s) for this practice")
            confirm = input("Delete them? (y/N): ").strip().lower()
            if confirm == 'y':
                PracticeRSVP.query.filter_by(practice_id=practice.id).delete()
                db.session.commit()
                print(f"Deleted {rsvp_count} RSVP(s)")

        print("\n" + "="*60)
        print("CLEANUP COMPLETE")
        print("="*60)
        print("\nNext step:")
        print("Run: python test_practice_post.py post-prod")


def post_prod():
    """Post practice announcement to production channel."""
    app = create_app()
    with app.app_context():
        practice = get_next_unposted_practice()
        if not practice:
            return

        if practice.slack_message_ts:
            print(f"Practice already has slack_message_ts: {practice.slack_message_ts}")
            print(f"Channel: {practice.slack_channel_id}")
            confirm = input("Post anyway (will overwrite)? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Aborted")
                return

        print(f"Posting practice #{practice.id} to production...")

        # Use the real function which posts to configured announcement channel
        result = post_practice_announcement(practice)

        if result.get('success'):
            print("\n" + "="*60)
            print("PRODUCTION POST COMPLETE")
            print("="*60)
            print(f"Message TS: {result.get('message_ts')}")
            print(f"Channel: {result.get('channel_id')}")
            print("\nPractice announcement is now live in #announcements-practices!")
        else:
            print(f"\nFailed to post: {result.get('error')}")


def update_prod():
    """Update existing production announcement with current block styling."""
    app = create_app()
    with app.app_context():
        practice = get_next_posted_practice()
        if not practice:
            return

        if not practice.slack_message_ts or not practice.slack_channel_id:
            print("Practice has no existing Slack message to update")
            print(f"  slack_message_ts: {practice.slack_message_ts}")
            print(f"  slack_channel_id: {practice.slack_channel_id}")
            return

        print(f"Practice #{practice.id}")
        print(f"  Channel: {practice.slack_channel_id}")
        print(f"  Message TS: {practice.slack_message_ts}")

        # Fetch weather if location has coordinates
        weather = None
        if practice.location and practice.location.latitude and practice.location.longitude:
            print(f"\nFetching weather for {practice.location.name}...")
            try:
                weather = get_weather_for_location(
                    practice.location.latitude,
                    practice.location.longitude,
                    practice.date
                )
                if weather:
                    print(f"  Temperature: {weather.temperature_f:.0f}°F")
                    if weather.conditions_summary:
                        print(f"  Conditions: {weather.conditions_summary}")
            except Exception as e:
                print(f"  Could not fetch weather: {e}")

        # Rebuild blocks with current styling
        practice_info = convert_practice_to_info(practice)
        blocks = build_practice_announcement_blocks(practice_info, weather=weather)

        print(f"\nUpdating message with {len(blocks)} blocks...")

        client = get_slack_client()
        try:
            response = client.chat_update(
                channel=practice.slack_channel_id,
                ts=practice.slack_message_ts,
                blocks=blocks,
                text=f"Practice on {practice.date.strftime('%A, %B %d')}"
            )

            # Add pre-seeded checkmark emoji for RSVP (if not already there)
            try:
                client.reactions_add(
                    channel=practice.slack_channel_id,
                    timestamp=practice.slack_message_ts,
                    name="white_check_mark"
                )
                print("Added checkmark emoji for RSVP")
            except Exception as e:
                # May already exist, that's fine
                if "already_reacted" not in str(e):
                    print(f"  Note: {e}")

            print("\n" + "="*60)
            print("PRODUCTION UPDATE COMPLETE")
            print("="*60)
            print("Message has been updated with current block styling!")
        except Exception as e:
            print(f"\nFailed to update: {e}")


def post_collab():
    """Post practice to #collab-coaches-practices for coach review/approval."""
    app = create_app()
    with app.app_context():
        practice = get_next_needs_collab_practice()
        if not practice:
            return

        print(f"Posting practice #{practice.id} to #collab-coaches-practices...")

        result = post_collab_review(practice)

        if result.get('success'):
            print("\n" + "="*60)
            print("COLLAB POST COMPLETE")
            print("="*60)
            print(f"Message TS: {result.get('message_ts')}")
            print(f"Channel: {result.get('channel_id')}")
            print("\nPractice is now in #collab-coaches-practices for coach review!")
        else:
            print(f"\nFailed to post: {result.get('error')}")


def get_lift_practices():
    """Get lift practices at Balance Fitness Studio for this week."""
    from datetime import datetime, timedelta

    # Find practices at Balance Fitness Studio in the next 7 days
    practices = Practice.query.filter(
        Practice.date >= datetime.now(),
        Practice.date <= datetime.now() + timedelta(days=7)
    ).order_by(Practice.date).all()

    # Filter to Balance Fitness Studio (lift location)
    lift_practices = [
        p for p in practices
        if p.location and 'balance' in p.location.name.lower()
    ]

    return lift_practices


def post_lift_test():
    """Post combined lift announcement to test channel."""
    app = create_app()
    with app.app_context():
        lift_practices = get_lift_practices()

        if not lift_practices:
            print("No lift practices found at Balance Fitness Studio this week")
            return

        print(f"Found {len(lift_practices)} lift practice(s):")
        for p in lift_practices:
            date_str = p.date.strftime('%a %b %-d %I:%M %p')
            print(f"  #{p.id}: {date_str}")

        # Convert to PracticeInfo
        practice_infos = [convert_practice_to_info(p) for p in lift_practices]

        # Build combined blocks
        blocks = build_combined_lift_blocks(practice_infos)

        # Post to test channel
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=TEST_CHANNEL,
            blocks=blocks,
            text="TCSC Lift Sessions",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        print(f"\nPosted to tcsc-devs! message_ts: {message_ts}")

        # Add both RSVP emojis
        rsvp_emojis = ["white_check_mark", "ballot_box_with_check"]
        for emoji in rsvp_emojis:
            try:
                client.reactions_add(
                    channel=TEST_CHANNEL,
                    timestamp=message_ts,
                    name=emoji
                )
                print(f"Added :{emoji}: emoji")
            except Exception as e:
                print(f"Could not add {emoji}: {e}")

        print("\n" + "="*60)
        print("LIFT TEST POST COMPLETE")
        print("="*60)
        print(f"Message TS: {message_ts}")
        print(f"Channel: {TEST_CHANNEL}")
        print("\nCheck #tcsc-devs to see the combined lift post!")
        print("RSVP with ✅ for first day, ☑️ for second day")


def post_lift_prod():
    """Post combined lift announcement to production channel."""
    app = create_app()
    with app.app_context():
        lift_practices = get_lift_practices()

        if not lift_practices:
            print("No lift practices found at Balance Fitness Studio this week")
            return

        print(f"Found {len(lift_practices)} lift practice(s):")
        for p in lift_practices:
            date_str = p.date.strftime('%a %b %-d %I:%M %p')
            print(f"  #{p.id}: {date_str}")

        # Convert to PracticeInfo
        practice_infos = [convert_practice_to_info(p) for p in lift_practices]

        # Build combined blocks
        blocks = build_combined_lift_blocks(practice_infos)

        # Post to production channel
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=PROD_CHANNEL,
            blocks=blocks,
            text="TCSC Lift Sessions",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        print(f"\nPosted to #announcements-practices! message_ts: {message_ts}")

        # Add both RSVP emojis
        rsvp_emojis = ["white_check_mark", "ballot_box_with_check"]
        for emoji in rsvp_emojis:
            try:
                client.reactions_add(
                    channel=PROD_CHANNEL,
                    timestamp=message_ts,
                    name=emoji
                )
                print(f"Added :{emoji}: emoji")
            except Exception as e:
                print(f"Could not add {emoji}: {e}")

        # Update the practice records with the message info
        for p in lift_practices:
            p.slack_message_ts = message_ts
            p.slack_channel_id = PROD_CHANNEL
        db.session.commit()
        print(f"Updated {len(lift_practices)} practice record(s) with channel info")

        print("\n" + "="*60)
        print("LIFT PRODUCTION POST COMPLETE")
        print("="*60)
        print(f"Message TS: {message_ts}")
        print(f"Channel: {PROD_CHANNEL}")


def update_lift_prod():
    """Update existing lift announcement in production channel."""
    app = create_app()
    with app.app_context():
        lift_practices = get_lift_practices()

        if not lift_practices:
            print("No lift practices found")
            return

        # Check if they have a shared message_ts
        first = lift_practices[0]
        if not first.slack_message_ts:
            print("No existing lift post to update")
            return

        print(f"Updating lift post: {first.slack_message_ts}")
        print(f"Channel: {first.slack_channel_id}")

        # Convert to PracticeInfo
        practice_infos = [convert_practice_to_info(p) for p in lift_practices]

        # Build combined blocks
        blocks = build_combined_lift_blocks(practice_infos)

        # Update the message
        client = get_slack_client()
        response = client.chat_update(
            channel=first.slack_channel_id,
            ts=first.slack_message_ts,
            blocks=blocks,
            text="TCSC Lift Sessions"
        )

        print("\n" + "="*60)
        print("LIFT UPDATE COMPLETE")
        print("="*60)


def post_coach_summary():
    """Post coach weekly review summary to test channel."""
    from datetime import datetime, timedelta
    from app.slack.practices import post_coach_weekly_summary
    from app.models import AppConfig

    app = create_app()
    with app.app_context():
        # Calculate start of upcoming week (next Monday)
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # If today is Monday, get next Monday
        week_start = (today + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        print(f"Posting coach weekly summary for week of {week_start.strftime('%B %d, %Y')}")
        print(f"Target channel: #tcsc-devs (TEST)")

        # Get expected practice days from config
        expected_days = AppConfig.get('practice_days', [
            {"day": "tuesday", "time": "18:00", "active": True},
            {"day": "thursday", "time": "18:00", "active": True},
            {"day": "saturday", "time": "09:00", "active": True}
        ])
        print(f"\nExpected practice days: {[d['day'] for d in expected_days if d.get('active', True)]}")

        # Get practices for the week
        week_end = week_start + timedelta(days=7)
        practices = Practice.query.filter(
            Practice.date >= week_start,
            Practice.date < week_end
        ).order_by(Practice.date).all()

        print(f"Found {len(practices)} practice(s) in database for this week")
        for p in practices:
            date_str = p.date.strftime('%a %b %-d %I:%M %p')
            loc = p.location.name if p.location else 'No location'
            print(f"  #{p.id}: {date_str} at {loc}")

        # Build the blocks
        practice_infos = [convert_practice_to_info(p) for p in practices]
        blocks = build_coach_weekly_summary_blocks(practice_infos, expected_days, week_start)
        print(f"\nGenerated {len(blocks)} blocks")

        # Post to test channel
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=TEST_CHANNEL,
            blocks=blocks,
            text=f"Coach Review: Week of {week_start.strftime('%B %d')}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        print(f"\nPosted to #tcsc-devs! message_ts: {message_ts}")

        # Save message_ts to practices so edit flow can update the summary
        for p in practices:
            p.slack_coach_summary_ts = message_ts
        db.session.commit()
        print(f"Linked {len(practices)} practice(s) to summary post")

        print("\n" + "="*60)
        print("COACH SUMMARY TEST POST COMPLETE")
        print("="*60)
        print(f"Message TS: {message_ts}")
        print(f"Channel: {TEST_CHANNEL}")
        print("\nCheck #tcsc-devs to see the coach weekly summary!")
        print("- Click 'Edit' to test editing a practice")
        print("- Click 'Add Practice' to test adding to a placeholder")


def post_coach_summary_prod():
    """Post coach weekly review summary to production collab channel."""
    from datetime import datetime, timedelta
    from app.slack.practices import post_coach_weekly_summary

    app = create_app()
    with app.app_context():
        # Calculate start of upcoming week (next Monday)
        today = datetime.now()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # If today is Monday, get next Monday
        week_start = (today + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        print(f"Posting coach weekly summary for week of {week_start.strftime('%B %d, %Y')}")
        print(f"Target channel: #collab-coaches-practices (PRODUCTION)")

        confirm = input("\nPost to production? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Aborted")
            return

        result = post_coach_weekly_summary(week_start)

        if result.get('success'):
            print("\n" + "="*60)
            print("COACH SUMMARY PRODUCTION POST COMPLETE")
            print("="*60)
            print(f"Message TS: {result.get('message_ts')}")
            print(f"Practices shown: {result.get('practices_shown', 0)}")
            print(f"Placeholders shown: {result.get('placeholders_shown', 0)}")
            print("\nCoach weekly summary is now live in #collab-coaches-practices!")
        else:
            print(f"\nFailed to post: {result.get('error')}")


def show_status():
    """Show current practice status."""
    app = create_app()
    with app.app_context():
        practice = get_next_unposted_practice()
        if not practice:
            return

        print(f"Practice #{practice.id} - {practice.date}")
        print(f"  Location: {practice.location.name if practice.location else 'None'}")
        print(f"  Status: {practice.status}")
        print(f"  slack_message_ts: {practice.slack_message_ts}")
        print(f"  slack_channel_id: {practice.slack_channel_id}")
        print(f"  slack_collab_message_ts: {practice.slack_collab_message_ts}")

        rsvp_count = PracticeRSVP.query.filter_by(practice_id=practice.id).count()
        going_count = PracticeRSVP.query.filter_by(practice_id=practice.id, status='going').count()
        print(f"  RSVPs: {rsvp_count} total, {going_count} going")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  post-test   - Post to tcsc-devs for testing")
        print("  cleanup     - Delete test post and clear DB")
        print("  post-prod   - Post to announcements-practices")
        print("  update-prod - Update existing production post with current styling")
        print("  post-collab - Post to collab-coaches-practices for review")
        print("  post-lift-test - Post combined lift to tcsc-devs for testing")
        print("  post-lift-prod - Post combined lift to announcements-practices")
        print("  update-lift-prod - Update existing lift post")
        print("  post-coach-summary - Post weekly coach summary to tcsc-devs")
        print("  post-coach-summary-prod - Post weekly coach summary to collab-coaches-practices")
        print("  status      - Show current practice status")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'post-test':
        post_test()
    elif command == 'cleanup':
        cleanup()
    elif command == 'post-prod':
        post_prod()
    elif command == 'update-prod':
        update_prod()
    elif command == 'post-collab':
        post_collab()
    elif command == 'post-lift-test':
        post_lift_test()
    elif command == 'post-lift-prod':
        post_lift_prod()
    elif command == 'update-lift-prod':
        update_lift_prod()
    elif command == 'post-coach-summary':
        post_coach_summary()
    elif command == 'post-coach-summary-prod':
        post_coach_summary_prod()
    elif command == 'status':
        show_status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
