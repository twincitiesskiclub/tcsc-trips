"""APScheduler setup for background jobs.

This module sets up a background scheduler that runs within the existing
web process (no separate worker needed). Jobs run in a thread pool while
web requests are handled normally.

Safety:
- Single-worker guard prevents duplicate job execution with Gunicorn
- Jobs are scheduled to run at specific times (Central time)
- All jobs respect dry_run config by default

Scheduled Jobs:
- 3:00 AM: Slack Channel Sync + ExpertVoice sync
- 7:00 AM: Skipper morning check (today's practices) → weather/conditions check
- 7:15 AM: Skipper 48h check (workout reminders) → posts to #collab-coaches-practices
- 7:30 AM: Skipper 24h check → DISABLED (replaced by 4pm/10pm lead checks)
- 4:00 PM: Evening lead check (noon-midnight today) → weather + lead verification
- 10:00 PM: Morning lead check (before noon tomorrow) → weather + lead verification
- 8:00 AM: Newsletter daily update → regenerates living post (weekly dispatch)
- 8:00 AM: Newsletter monthly orchestrator → day-of-month-based actions
- 8:00 AM Sunday: Coach weekly review summary (collab-coaches-practices)
- 6:00 PM Sunday: Newsletter finalize → marks ready for review
- 8:30 PM Sunday: Weekly practice summary (announcements-practices)
- Hourly: Expire pending cancellation proposals (fail-open)
"""
import os
import fcntl
import atexit
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask


# Lock file for single-worker guard
LOCK_FILE = '/tmp/tcsc_scheduler.lock'
_lock_fd = None

# Global scheduler instance
scheduler = BackgroundScheduler()


def is_main_worker() -> bool:
    """Check if this is the main worker that should run the scheduler.

    Uses a file lock to ensure only one Gunicorn worker starts the scheduler.
    The first worker to acquire the lock becomes the "main" worker.

    Returns:
        True if this worker should run the scheduler.
    """
    global _lock_fd

    try:
        _lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        # Another worker has the lock
        if _lock_fd:
            _lock_fd.close()
            _lock_fd = None
        return False


def release_lock():
    """Release the scheduler lock on shutdown."""
    global _lock_fd
    if _lock_fd:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None


def run_channel_sync_job(app: Flask):
    """Execute the channel sync job within app context.

    This function is called by APScheduler at the scheduled time.
    It runs both the Slack channel sync and ExpertVoice sync.

    Args:
        app: Flask application instance for context.
    """
    with app.app_context():
        from app.slack.channel_sync import run_channel_sync
        from app.integrations.expertvoice import sync_expertvoice

        app.logger.info("=" * 60)
        app.logger.info("Starting scheduled channel sync job")
        app.logger.info(f"Time: {datetime.now().isoformat()}")
        app.logger.info("=" * 60)

        try:
            # Run Slack channel sync
            app.logger.info("Running Slack channel sync...")
            sync_result = run_channel_sync()

            app.logger.info(
                f"Slack sync complete: "
                f"processed={sync_result.total_processed}, "
                f"role_changes={sync_result.role_changes}, "
                f"channel_adds={sync_result.channel_adds}, "
                f"channel_removals={sync_result.channel_removals}, "
                f"invites={sync_result.invites_sent}, "
                f"errors={len(sync_result.errors)}"
            )

            if sync_result.errors:
                for error in sync_result.errors[:5]:
                    app.logger.warning(f"Sync error: {error}")
                if len(sync_result.errors) > 5:
                    app.logger.warning(f"... and {len(sync_result.errors) - 5} more errors")

        except Exception as e:
            app.logger.error(f"Slack channel sync failed: {e}", exc_info=True)

        try:
            # Run ExpertVoice sync
            app.logger.info("Running ExpertVoice sync...")
            ev_result = sync_expertvoice()

            app.logger.info(
                f"ExpertVoice sync complete: "
                f"members={ev_result.members_synced}, "
                f"uploaded={ev_result.uploaded}, "
                f"errors={len(ev_result.errors)}"
            )

        except Exception as e:
            app.logger.error(f"ExpertVoice sync failed: {e}", exc_info=True)

        app.logger.info("=" * 60)
        app.logger.info("Scheduled channel sync job complete")
        app.logger.info("=" * 60)


def run_skipper_morning_check_job(app: Flask, channel_override: str = None):
    """Execute the morning practice check job within app context.

    Runs at 7am daily to evaluate all practices scheduled for today.
    Creates cancellation proposals for practices with unsafe conditions.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from app.agent.routines.morning_check import run_morning_check
        from app.agent.proposals import expire_pending_proposals

        app.logger.info("=" * 60)
        app.logger.info("Starting Skipper morning check job")
        app.logger.info(f"Time: {datetime.now().isoformat()}")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        try:
            # First, expire any pending proposals from yesterday
            expired = expire_pending_proposals()
            if expired:
                app.logger.info(f"Expired {len(expired)} pending proposals (fail-open)")

            # Run morning check
            result = run_morning_check(channel_override=channel_override)

            app.logger.info(
                f"Morning check complete: "
                f"checked={result.get('checked', 0)}, "
                f"safe={result.get('safe', 0)}, "
                f"proposals={result.get('proposals_created', 0)}, "
                f"errors={result.get('errors', 0)}"
            )

        except Exception as e:
            app.logger.error(f"Skipper morning check failed: {e}", exc_info=True)

        app.logger.info("=" * 60)
        app.logger.info("Skipper morning check job complete")
        app.logger.info("=" * 60)


def run_skipper_48h_check_job(app: Flask, channel_override: str = None):
    """Execute the 48-hour pre-practice check job within app context.

    Runs at 7:15am daily to nudge coaches for workout submission.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from app.agent.routines.pre_practice import run_48h_check

        app.logger.info("Starting Skipper 48h check job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")

        try:
            result = run_48h_check(channel_override=channel_override)

            app.logger.info(
                f"48h check complete: "
                f"checked={result.get('checked', 0)}, "
                f"needs_workout={result.get('needs_workout', 0)}, "
                f"nudges_sent={result.get('nudges_sent', 0)}"
            )

        except Exception as e:
            app.logger.error(f"Skipper 48h check failed: {e}", exc_info=True)


def run_skipper_24h_check_job(app: Flask, channel_override: str = None):
    """Execute the 24-hour pre-practice check job within app context.

    Runs at 7:30am daily to confirm lead availability and provide weather updates.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from app.agent.routines.pre_practice import run_24h_check

        app.logger.info("Starting Skipper 24h check job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")

        try:
            result = run_24h_check(channel_override=channel_override)

            app.logger.info(
                f"24h check complete: "
                f"checked={result.get('checked', 0)}, "
                f"confirmed={result.get('confirmed', 0)}, "
                f"weather_updates={result.get('weather_updates', 0)}"
            )

        except Exception as e:
            app.logger.error(f"Skipper 24h check failed: {e}", exc_info=True)


def run_lead_check_job(app: Flask, check_type: str, channel_override: str = None):
    """Execute a lead verification check within app context.

    Args:
        app: Flask application instance for context.
        check_type: Either 'evening' (4pm) or 'morning' (10pm).
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from app.agent.routines.lead_verification import (
            run_evening_lead_check,
            run_morning_lead_check
        )

        check_fn = run_evening_lead_check if check_type == 'evening' else run_morning_lead_check
        time_label = "4pm evening" if check_type == 'evening' else "10pm morning"

        app.logger.info("=" * 60)
        app.logger.info(f"Starting {time_label} lead verification check")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        try:
            result = check_fn(channel_override=channel_override)

            app.logger.info(
                f"{check_type.title()} lead check complete: "
                f"checked={result.get('checked', 0)}, "
                f"safe={result.get('safe', 0)}, "
                f"proposals={result.get('proposals_created', 0)}, "
                f"dms_sent={result.get('dms_sent', 0)}"
            )

        except Exception as e:
            app.logger.error(f"{check_type.title()} lead check failed: {e}", exc_info=True)


def run_weekly_summary_job(app: Flask, channel_override: str = None):
    """Execute the weekly practice summary job within app context.

    Runs Sunday at 6pm to post upcoming week's practices to Slack.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from app.agent.routines.weekly_summary import run_weekly_summary

        app.logger.info("=" * 60)
        app.logger.info("Starting weekly practice summary job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        try:
            result = run_weekly_summary(channel_override=channel_override)

            app.logger.info(
                f"Weekly summary complete: "
                f"{result.get('practice_count', 0)} practices for week of "
                f"{result.get('week_start', 'unknown')}"
            )

        except Exception as e:
            app.logger.error(f"Weekly summary failed: {e}", exc_info=True)


def run_coach_weekly_summary_job(app: Flask, channel_override: str = None):
    """Execute the coach weekly review summary job within app context.

    Runs Sunday at 6pm to post a summary of the upcoming week's practices
    to #collab-coaches-practices with Edit buttons for each practice.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    with app.app_context():
        from datetime import timedelta
        from app.slack.practices import post_coach_weekly_summary

        app.logger.info("=" * 60)
        app.logger.info("Starting coach weekly review summary job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        try:
            # Calculate the start of the upcoming week (Monday)
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7  # If today is Monday, get next Monday
            week_start = (today + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            result = post_coach_weekly_summary(week_start, channel_override=channel_override)

            if result.get('success'):
                app.logger.info(
                    f"Coach weekly summary posted: "
                    f"{result.get('practices_shown', 0)} practices, "
                    f"{result.get('placeholders_shown', 0)} placeholders"
                )
            else:
                app.logger.error(f"Coach weekly summary failed: {result.get('error')}")

        except Exception as e:
            app.logger.error(f"Coach weekly summary failed: {e}", exc_info=True)


def run_expire_proposals_job(app: Flask):
    """Expire pending cancellation proposals that have timed out.

    Implements fail-open behavior: if no human decision is made within
    the timeout window, the practice continues as scheduled.

    Args:
        app: Flask application instance for context.
    """
    with app.app_context():
        from app.agent.proposals import expire_pending_proposals

        try:
            expired = expire_pending_proposals()
            if expired:
                app.logger.info(f"Expired {len(expired)} pending proposals (fail-open)")

        except Exception as e:
            app.logger.error(f"Expire proposals failed: {e}", exc_info=True)


def _is_strength_practice(practice) -> bool:
    """Check if a practice has the 'Strength' practice type."""
    return any(
        pt.name.lower() == 'strength'
        for pt in practice.practice_types
    )


def _get_upcoming_strength_practices(now, app) -> list:
    """Get all unannounced strength practices in the next 7 days.

    Used to combine multiple strength/lift practices into a single announcement.
    """
    from datetime import timedelta
    from app.practices.models import Practice
    from app.practices.interfaces import PracticeStatus

    week_end = now + timedelta(days=7)

    practices = Practice.query.filter(
        Practice.date >= now,
        Practice.date <= week_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ]),
        Practice.slack_message_ts.is_(None)  # Not yet announced
    ).order_by(Practice.date).all()

    strength_practices = [p for p in practices if _is_strength_practice(p)]
    app.logger.info(f"Found {len(strength_practices)} unannounced strength practices in next 7 days")

    return strength_practices


def run_practice_announcements_job(app: Flask, channel_override: str = None):
    """Execute the daily practice announcement job within app context.

    Posts practice announcements with smart timing:
    - Evening practices (12pm+): Run at 8am, announce same day
    - Morning practices (before 12pm): Run at 8pm, announce for tomorrow

    Strength practices (lift workouts) are combined into a single announcement
    when multiple are found in the upcoming week.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    with app.app_context():
        from app.practices.models import Practice
        from app.practices.interfaces import PracticeStatus
        from app.slack.practices import post_practice_announcement, post_combined_lift_announcement

        app.logger.info("=" * 60)
        app.logger.info("Starting practice announcements job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        # Use Central timezone for logic (matches scheduler trigger timezone)
        # Convert to naive datetime for database comparisons (Practice.date is naive)
        central_tz = ZoneInfo('America/Chicago')
        now_central = datetime.now(central_tz)
        now = now_central.replace(tzinfo=None)  # Naive datetime in Central time
        app.logger.info(f"Current time (Central): {now_central.strftime('%Y-%m-%d %H:%M %Z')}")
        practices_to_announce = []

        try:
            if now.hour < 12:
                # Morning run (around 8am): Announce evening practices for today
                today_start = now.replace(hour=12, minute=0, second=0, microsecond=0)
                today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
                app.logger.info(f"Morning run: Looking for practices between {today_start} and {today_end}")

                practices = Practice.query.filter(
                    Practice.date >= today_start,
                    Practice.date <= today_end,
                    Practice.status.in_([
                        PracticeStatus.SCHEDULED.value,
                        PracticeStatus.CONFIRMED.value
                    ]),
                    Practice.slack_message_ts.is_(None)  # Not yet announced
                ).order_by(Practice.date).all()

                app.logger.info(f"Morning run: Found {len(practices)} evening practices to announce")
                practices_to_announce.extend(practices)

            else:
                # Evening run (around 8pm): Announce morning practices for tomorrow
                tomorrow_start = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                tomorrow_noon = tomorrow_start.replace(hour=12)
                app.logger.info(f"Evening run: Looking for practices between {tomorrow_start} and {tomorrow_noon}")

                practices = Practice.query.filter(
                    Practice.date >= tomorrow_start,
                    Practice.date < tomorrow_noon,
                    Practice.status.in_([
                        PracticeStatus.SCHEDULED.value,
                        PracticeStatus.CONFIRMED.value
                    ]),
                    Practice.slack_message_ts.is_(None)  # Not yet announced
                ).order_by(Practice.date).all()

                app.logger.info(f"Evening run: Found {len(practices)} morning practices to announce")
                practices_to_announce.extend(practices)

            # Separate strength practices from regular practices
            strength_in_window = [p for p in practices_to_announce if _is_strength_practice(p)]
            regular_practices = [p for p in practices_to_announce if not _is_strength_practice(p)]

            announced = 0
            errors = 0

            # Handle strength practices: combine if any are in this announcement window
            if strength_in_window:
                # Get ALL unannounced strength practices in next 7 days to combine
                all_strength = _get_upcoming_strength_practices(now, app)

                if len(all_strength) >= 2:
                    # Combine multiple strength practices into one announcement
                    app.logger.info(f"Combining {len(all_strength)} strength practices into single announcement")
                    try:
                        result = post_combined_lift_announcement(
                            all_strength,
                            channel_override=channel_override
                        )
                        if result.get('success'):
                            announced += len(all_strength)
                            practice_ids = [p.id for p in all_strength]
                            app.logger.info(f"Announced combined strength practices: {practice_ids}")
                        else:
                            errors += len(all_strength)
                            app.logger.error(f"Failed to announce combined strength practices: {result.get('error')}")
                    except Exception as e:
                        errors += len(all_strength)
                        app.logger.error(f"Error announcing combined strength practices: {e}", exc_info=True)
                else:
                    # Only one strength practice, post individually
                    for practice in strength_in_window:
                        try:
                            result = post_practice_announcement(
                                practice,
                                channel_override=channel_override
                            )
                            if result.get('success'):
                                announced += 1
                                app.logger.info(f"Announced strength practice #{practice.id}")
                            else:
                                errors += 1
                                app.logger.error(f"Failed to announce practice #{practice.id}: {result.get('error')}")
                        except Exception as e:
                            errors += 1
                            app.logger.error(f"Error announcing practice #{practice.id}: {e}", exc_info=True)

            # Announce regular (non-strength) practices individually
            for practice in regular_practices:
                try:
                    result = post_practice_announcement(
                        practice,
                        channel_override=channel_override
                    )
                    if result.get('success'):
                        announced += 1
                        app.logger.info(f"Announced practice #{practice.id}")
                    else:
                        errors += 1
                        app.logger.error(f"Failed to announce practice #{practice.id}: {result.get('error')}")
                except Exception as e:
                    errors += 1
                    app.logger.error(f"Error announcing practice #{practice.id}: {e}", exc_info=True)

            app.logger.info(f"Practice announcements complete: announced={announced}, errors={errors}")

        except Exception as e:
            app.logger.error(f"Practice announcements job failed: {e}", exc_info=True)

        app.logger.info("=" * 60)
        app.logger.info("Practice announcements job complete")
        app.logger.info("=" * 60)


def run_newsletter_daily_job(app: Flask):
    """Execute the newsletter daily update job within app context.

    Runs at 8am daily to regenerate the newsletter with latest content
    from Slack channels and external news sources.

    Args:
        app: Flask application instance for context.
    """
    with app.app_context():
        from app.newsletter.service import run_daily_update

        app.logger.info("=" * 60)
        app.logger.info("Starting newsletter daily update job")
        app.logger.info(f"Time: {datetime.now().isoformat()}")
        app.logger.info("=" * 60)

        try:
            result = run_daily_update()

            if result.get('skipped'):
                app.logger.info(f"Newsletter daily update skipped: {result.get('reason')}")
            else:
                app.logger.info(
                    f"Newsletter daily update complete: "
                    f"newsletter_id={result.get('newsletter_id')}, "
                    f"version={result.get('version_number')}, "
                    f"messages={result.get('messages_collected', 0)}, "
                    f"news_items={result.get('news_items_scraped', 0)}"
                )

            if result.get('errors'):
                for error in result['errors'][:5]:
                    app.logger.warning(f"Newsletter error: {error}")

        except Exception as e:
            app.logger.error(f"Newsletter daily update failed: {e}", exc_info=True)

        app.logger.info("=" * 60)
        app.logger.info("Newsletter daily update job complete")
        app.logger.info("=" * 60)


def run_newsletter_sunday_job(app: Flask):
    """Execute the newsletter Sunday finalization job within app context.

    Runs at 6pm on Sundays to finalize the newsletter and mark it
    ready for admin review before publication.

    Args:
        app: Flask application instance for context.
    """
    with app.app_context():
        from app.newsletter.service import run_sunday_finalize

        app.logger.info("=" * 60)
        app.logger.info("Starting newsletter Sunday finalization job")
        app.logger.info(f"Time: {datetime.now().isoformat()}")
        app.logger.info("=" * 60)

        try:
            result = run_sunday_finalize()

            if result.get('skipped'):
                app.logger.info(f"Newsletter finalization skipped: {result.get('reason')}")
            else:
                app.logger.info(
                    f"Newsletter finalization complete: "
                    f"newsletter_id={result.get('newsletter_id')}, "
                    f"status={result.get('previous_status')} -> {result.get('new_status')}"
                )

            if result.get('errors'):
                for error in result['errors'][:5]:
                    app.logger.warning(f"Newsletter error: {error}")

        except Exception as e:
            app.logger.error(f"Newsletter Sunday finalization failed: {e}", exc_info=True)

        app.logger.info("=" * 60)
        app.logger.info("Newsletter Sunday finalization job complete")
        app.logger.info("=" * 60)


def run_newsletter_monthly_orchestrator_job(app: Flask):
    """Execute the newsletter monthly orchestrator job within app context.

    Runs daily at 8am CT to check what day-of-month-specific actions
    need to happen for the Monthly Dispatch newsletter.

    Monthly Schedule:
    - Day 1: Send host DM (if assigned), assign coach (automated), post QOTM
    - Day 5: Send member highlight request (if nominated)
    - Day 10: Coach reminder (if not submitted), host reminder (if not submitted)
    - Day 12: Generate AI drafts, create living post
    - Day 13: Send final reminders
    - Day 14: Add review/edit buttons
    - Day 15: Manual publish (admin approval required)

    Args:
        app: Flask application instance for context.
    """
    from zoneinfo import ZoneInfo

    with app.app_context():
        from app.newsletter.models import Newsletter

        # Use Central timezone to determine day of month
        central_tz = ZoneInfo('America/Chicago')
        now_central = datetime.now(central_tz)
        today = now_central.day

        app.logger.info("=" * 60)
        app.logger.info("Starting newsletter monthly orchestrator job")
        app.logger.info(f"Time: {now_central.strftime('%Y-%m-%d %H:%M %Z')}")
        app.logger.info(f"Day of month: {today}")
        app.logger.info("=" * 60)

        # Get or create newsletter for current month
        try:
            newsletter = Newsletter.get_or_create_current_month()
            from app.models import db
            db.session.commit()
            app.logger.info(
                f"Newsletter: id={newsletter.id}, "
                f"month={newsletter.month_year}, "
                f"status={newsletter.status}"
            )
        except Exception as e:
            app.logger.error(f"Failed to get/create newsletter: {e}", exc_info=True)
            return

        # ====================================================================
        # Day 1: Host DM, Coach assignment, QOTM post
        # ====================================================================
        if today == 1:
            app.logger.info("Day 1 actions: Host DM, Coach assignment, QOTM post")

            # Send host request DM (if host has been assigned manually)
            try:
                if newsletter.host:
                    from app.newsletter.host import send_host_request
                    result = send_host_request(newsletter.id)
                    if result.get('success'):
                        app.logger.info(
                            f"Sent host request DM (channel={result.get('channel_id')})"
                        )
                    elif result.get('error'):
                        app.logger.warning(f"Host request DM failed: {result.get('error')}")
                else:
                    app.logger.info("No host assigned yet, skipping host DM")
            except Exception as e:
                app.logger.error(f"Host request failed: {e}", exc_info=True)

            # Assign coach (automated rotation)
            try:
                from app.newsletter.coach_rotation import (
                    assign_coach_for_month,
                    send_coach_request,
                )
                assign_result = assign_coach_for_month(newsletter.id)
                if assign_result.get('success'):
                    app.logger.info(
                        f"Assigned coach: {assign_result.get('coach_name')}"
                    )
                    # Send coach request DM
                    dm_result = send_coach_request(newsletter.id)
                    if dm_result.get('success'):
                        app.logger.info(
                            f"Sent coach request DM (channel={dm_result.get('channel_id')})"
                        )
                    else:
                        app.logger.warning(
                            f"Coach request DM failed: {dm_result.get('error')}"
                        )
                else:
                    app.logger.warning(
                        f"Coach assignment failed: {assign_result.get('error')}"
                    )
            except Exception as e:
                app.logger.error(f"Coach assignment failed: {e}", exc_info=True)

            # Post QOTM to #chat
            try:
                if newsletter.qotm_question:
                    from app.newsletter.qotm import post_qotm_to_channel
                    result = post_qotm_to_channel(
                        newsletter.id,
                        newsletter.qotm_question,
                        channel='chat'
                    )
                    if result.get('success'):
                        app.logger.info(
                            f"Posted QOTM to #chat (ts={result.get('message_ts')})"
                        )
                    else:
                        app.logger.warning(f"QOTM post failed: {result.get('error')}")
                else:
                    app.logger.info("No QOTM question set, skipping QOTM post")
            except Exception as e:
                app.logger.error(f"QOTM post failed: {e}", exc_info=True)

        # ====================================================================
        # Day 5: Member highlight request (if nominated)
        # ====================================================================
        elif today == 5:
            app.logger.info("Day 5 actions: Member highlight request")

            try:
                if newsletter.has_highlight_nomination:
                    from app.newsletter.member_highlight import send_highlight_request
                    result = send_highlight_request(newsletter.id)
                    if result.get('success'):
                        app.logger.info(
                            f"Sent highlight request DM (channel={result.get('channel_id')})"
                        )
                    else:
                        app.logger.warning(
                            f"Highlight request failed: {result.get('error')}"
                        )
                else:
                    app.logger.info("No member highlight nomination, skipping")
            except Exception as e:
                app.logger.error(f"Highlight request failed: {e}", exc_info=True)

        # ====================================================================
        # Day 10: Reminders for coach and host
        # ====================================================================
        elif today == 10:
            app.logger.info("Day 10 actions: Coach and host reminders")

            # Send coach reminder if not submitted
            try:
                from app.newsletter.coach_rotation import send_coach_reminder
                result = send_coach_reminder(newsletter.id)
                if result.get('success'):
                    if result.get('skipped'):
                        app.logger.info(f"Coach reminder skipped: {result.get('reason')}")
                    else:
                        app.logger.info(
                            f"Sent coach reminder (channel={result.get('channel_id')})"
                        )
                else:
                    app.logger.warning(f"Coach reminder failed: {result.get('error')}")
            except Exception as e:
                app.logger.error(f"Coach reminder failed: {e}", exc_info=True)

            # Send host reminder if not submitted
            try:
                from app.newsletter.host import send_host_reminder
                result = send_host_reminder(newsletter.id)
                if result.get('success'):
                    if result.get('skipped'):
                        app.logger.info(f"Host reminder skipped: {result.get('reason')}")
                    else:
                        app.logger.info(
                            f"Sent host reminder (channel={result.get('channel_id')})"
                        )
                else:
                    app.logger.warning(f"Host reminder failed: {result.get('error')}")
            except Exception as e:
                app.logger.error(f"Host reminder failed: {e}", exc_info=True)

        # ====================================================================
        # Day 12: Generate AI drafts and create living post
        # ====================================================================
        elif today == 12:
            app.logger.info("Day 12 actions: Generate AI drafts, create living post")

            # Generate AI drafts (including Member Highlight AI composition)
            # Note: generate_ai_drafts() doesn't exist yet - wrap in try/except
            try:
                # Try to compose member highlight with AI if submitted
                from app.newsletter.member_highlight import compose_highlight_with_ai
                from app.newsletter.interfaces import HighlightStatus

                highlight = newsletter.highlight if hasattr(newsletter, 'highlight') else None
                if highlight and highlight.status == HighlightStatus.SUBMITTED.value:
                    result = compose_highlight_with_ai(newsletter.id)
                    if result.get('success'):
                        app.logger.info(
                            f"Composed member highlight with AI "
                            f"(highlight_id={result.get('highlight_id')})"
                        )
                    else:
                        app.logger.warning(
                            f"AI highlight composition failed: {result.get('error')}"
                        )
                else:
                    app.logger.info("No submitted highlight to compose with AI")
            except Exception as e:
                app.logger.error(f"AI draft generation failed: {e}", exc_info=True)

            # Create/update living post
            # Note: This uses the existing slack_actions module
            try:
                from app.newsletter.slack_actions import (
                    create_living_post,
                    update_living_post,
                    is_dry_run,
                )

                if is_dry_run():
                    app.logger.info("[DRY RUN] Would create/update living post")
                else:
                    # Build content dict for the living post
                    # This is a simplified version - real implementation would
                    # aggregate all section content
                    content = _build_monthly_dispatch_content(newsletter, app)

                    if not newsletter.slack_main_message_ts:
                        post_ref = create_living_post(newsletter, content)
                        app.logger.info(
                            f"Created living post (ts={post_ref.message_ts})"
                        )
                    else:
                        post_ref = update_living_post(newsletter, content)
                        app.logger.info(
                            f"Updated living post (ts={post_ref.message_ts})"
                        )
            except Exception as e:
                app.logger.error(f"Living post creation failed: {e}", exc_info=True)

        # ====================================================================
        # Day 13: Final reminders
        # ====================================================================
        elif today == 13:
            app.logger.info("Day 13 actions: Final reminders")

            # Send final reminders for any missing content
            # Re-use the reminder functions from day 10

            # Coach final reminder
            try:
                from app.newsletter.coach_rotation import send_coach_reminder
                result = send_coach_reminder(newsletter.id)
                if result.get('success') and not result.get('skipped'):
                    app.logger.info(
                        f"Sent final coach reminder (channel={result.get('channel_id')})"
                    )
                elif result.get('skipped'):
                    app.logger.info(f"Coach reminder skipped: {result.get('reason')}")
            except Exception as e:
                app.logger.error(f"Final coach reminder failed: {e}", exc_info=True)

            # Host final reminder
            try:
                from app.newsletter.host import send_host_reminder
                result = send_host_reminder(newsletter.id)
                if result.get('success') and not result.get('skipped'):
                    app.logger.info(
                        f"Sent final host reminder (channel={result.get('channel_id')})"
                    )
                elif result.get('skipped'):
                    app.logger.info(f"Host reminder skipped: {result.get('reason')}")
            except Exception as e:
                app.logger.error(f"Final host reminder failed: {e}", exc_info=True)

        # ====================================================================
        # Day 14: Add review/edit buttons
        # ====================================================================
        elif today == 14:
            app.logger.info("Day 14 actions: Add review buttons")

            try:
                from app.newsletter.slack_actions import add_review_buttons, is_dry_run

                if is_dry_run():
                    app.logger.info("[DRY RUN] Would add review buttons")
                else:
                    success = add_review_buttons(newsletter)
                    if success:
                        app.logger.info("Added review/edit buttons to living post")
                    else:
                        app.logger.warning("Failed to add review buttons")
            except Exception as e:
                app.logger.error(f"Add review buttons failed: {e}", exc_info=True)

        # ====================================================================
        # Other days: No automated actions
        # ====================================================================
        else:
            app.logger.info(f"No automated actions scheduled for day {today}")

        app.logger.info("=" * 60)
        app.logger.info("Newsletter monthly orchestrator job complete")
        app.logger.info("=" * 60)


def _build_monthly_dispatch_content(newsletter, app) -> dict:
    """Build content dict for Monthly Dispatch living post.

    Aggregates content from all newsletter sections into a structured
    dict that can be rendered by the Block Kit templates.

    Args:
        newsletter: Newsletter instance
        app: Flask app for logging

    Returns:
        Dict with section content for template rendering
    """
    content = {
        'month_year': newsletter.month_year,
        'status': newsletter.status,
        'sections': {}
    }

    # Opener from host
    if newsletter.host and newsletter.host.opener_content:
        content['sections']['opener'] = {
            'content': newsletter.host.opener_content,
            'author': newsletter.host.display_name,
        }

    # Coaches Corner
    if newsletter.coach_rotation and newsletter.coach_rotation.content:
        coach = newsletter.coach_rotation.coach
        content['sections']['coaches_corner'] = {
            'content': newsletter.coach_rotation.content,
            'author': coach.full_name if coach else 'Anonymous Coach',
        }

    # Member Highlight
    highlight = newsletter.highlight if hasattr(newsletter, 'highlight') else None
    if highlight:
        # Prefer final edited content, then AI composed, then raw
        highlight_content = (
            highlight.content or
            highlight.ai_composed_content or
            str(highlight.raw_answers)
        )
        member = highlight.member
        content['sections']['member_highlight'] = {
            'content': highlight_content,
            'member_name': member.full_name if member else 'Featured Member',
        }

    # QOTM and responses
    if newsletter.qotm_question:
        from app.newsletter.qotm import get_selected_qotm_for_newsletter
        selected_responses = get_selected_qotm_for_newsletter(newsletter.id)
        content['sections']['qotm'] = {
            'question': newsletter.qotm_question,
            'responses': [
                {'user_name': r.user_name, 'response': r.response}
                for r in selected_responses
            ]
        }

    # Closer from host
    if newsletter.host and newsletter.host.closer_content:
        content['sections']['closer'] = {
            'content': newsletter.host.closer_content,
            'author': newsletter.host.display_name,
        }

    return content


def init_scheduler(app: Flask) -> bool:
    """Initialize the scheduler within the Flask application.

    This should be called once during app initialization. It sets up
    the scheduler and registers jobs, but only starts the scheduler
    in the main worker (for Gunicorn deployments).

    Args:
        app: Flask application instance.

    Returns:
        True if scheduler was started, False if skipped.
    """
    # Skip in development reload subprocess
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # This is the reloader child process in development
        # Only start scheduler here to avoid duplicate
        pass
    elif os.environ.get('WERKZEUG_RUN_MAIN') is None:
        # Not using Werkzeug reloader (production or direct run)
        pass
    else:
        # Parent reloader process - skip
        app.logger.info("Skipping scheduler in reloader parent process")
        return False

    # Check for single-worker guard (Gunicorn multi-worker)
    if not is_main_worker():
        app.logger.info("Scheduler: Not main worker, skipping initialization")
        return False

    # Register cleanup on shutdown
    atexit.register(release_lock)
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)

    # Check if scheduler is already running (shouldn't happen, but safety check)
    if scheduler.running:
        app.logger.warning("Scheduler already running, skipping initialization")
        return False

    # Schedule the channel sync job
    # Runs daily at 3:00 AM US Central time
    scheduler.add_job(
        func=run_channel_sync_job,
        args=[app],
        trigger=CronTrigger(
            hour=3,
            minute=0,
            timezone='America/Chicago'  # US Central
        ),
        id='slack_channel_sync',
        name='Slack Channel Sync',
        replace_existing=True,
        misfire_grace_time=3600  # Run if missed by up to 1 hour
    )

    # ========================================================================
    # Skipper Practice Monitoring Jobs
    # ========================================================================

    # Morning check: Evaluate today's practices at 7:00 AM
    scheduler.add_job(
        func=run_skipper_morning_check_job,
        args=[app],
        trigger=CronTrigger(
            hour=7,
            minute=0,
            timezone='America/Chicago'
        ),
        id='skipper_morning_check',
        name='Skipper Morning Check',
        replace_existing=True,
        misfire_grace_time=1800  # 30 min grace
    )

    # 48h check: Nudge coaches for workouts at 7:15 AM
    scheduler.add_job(
        func=run_skipper_48h_check_job,
        args=[app],
        trigger=CronTrigger(
            hour=7,
            minute=15,
            timezone='America/Chicago'
        ),
        id='skipper_48h_check',
        name='Skipper 48h Check',
        replace_existing=True,
        misfire_grace_time=1800
    )

    # 24h check: DISABLED - Lead confirmation now uses reaction-based system
    # The 4pm and 10pm checks handle lead verification via practice post reactions
    # Keeping job function for manual triggering if needed, but not scheduled
    # scheduler.add_job(
    #     func=run_skipper_24h_check_job,
    #     args=[app],
    #     trigger=CronTrigger(
    #         hour=7,
    #         minute=30,
    #         timezone='America/Chicago'
    #     ),
    #     id='skipper_24h_check',
    #     name='Skipper 24h Check',
    #     replace_existing=True,
    #     misfire_grace_time=1800
    # )

    # 4pm evening check: Verify leads for evening practices (noon to midnight today)
    scheduler.add_job(
        func=run_lead_check_job,
        args=[app, 'evening'],
        trigger=CronTrigger(
            hour=16,
            minute=0,
            timezone='America/Chicago'
        ),
        id='skipper_evening_lead_check',
        name='Skipper Evening Lead Check',
        replace_existing=True,
        misfire_grace_time=1800  # 30 min grace
    )

    # 10pm morning check: Verify leads for morning practices (before noon tomorrow)
    scheduler.add_job(
        func=run_lead_check_job,
        args=[app, 'morning'],
        trigger=CronTrigger(
            hour=22,
            minute=0,
            timezone='America/Chicago'
        ),
        id='skipper_morning_lead_check',
        name='Skipper Morning Lead Check',
        replace_existing=True,
        misfire_grace_time=1800  # 30 min grace
    )

    # Weekly summary: Post upcoming week on Sunday at 8:30 PM
    scheduler.add_job(
        func=run_weekly_summary_job,
        args=[app],
        trigger=CronTrigger(
            day_of_week='sun',
            hour=20,
            minute=30,
            timezone='America/Chicago'
        ),
        id='skipper_weekly_summary',
        name='Weekly Practice Summary',
        replace_existing=True,
        misfire_grace_time=3600
    )

    # Coach weekly review: Post to collab-coaches-practices on Sunday at 8:00 AM
    scheduler.add_job(
        func=run_coach_weekly_summary_job,
        args=[app],
        trigger=CronTrigger(
            day_of_week='sun',
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='coach_weekly_summary',
        name='Coach Weekly Review Summary',
        replace_existing=True,
        misfire_grace_time=3600
    )

    # Expire proposals: Check hourly for timed-out proposals (fail-open)
    scheduler.add_job(
        func=run_expire_proposals_job,
        args=[app],
        trigger=CronTrigger(
            minute=0,  # Every hour on the hour
            timezone='America/Chicago'
        ),
        id='skipper_expire_proposals',
        name='Expire Proposals (Fail-Open)',
        replace_existing=True
    )

    # ========================================================================
    # Practice Announcements (smart timing)
    # ========================================================================

    # Morning announcement run: 8:00 AM for evening practices (today)
    scheduler.add_job(
        func=run_practice_announcements_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='practice_announcements_morning',
        name='Practice Announcements (Morning)',
        replace_existing=True,
        misfire_grace_time=1800
    )

    # Evening announcement run: 8:00 PM for morning practices (tomorrow)
    scheduler.add_job(
        func=run_practice_announcements_job,
        args=[app],
        trigger=CronTrigger(
            hour=20,
            minute=0,
            timezone='America/Chicago'
        ),
        id='practice_announcements_evening',
        name='Practice Announcements (Evening)',
        replace_existing=True,
        misfire_grace_time=1800
    )

    # ========================================================================
    # Newsletter Jobs (Weekly Dispatch)
    # ========================================================================

    # Newsletter daily update: 8:00 AM daily (after practice announcements)
    scheduler.add_job(
        func=run_newsletter_daily_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='newsletter_daily_update',
        name='Newsletter Daily Update',
        replace_existing=True,
        misfire_grace_time=3600  # 1 hour grace
    )

    # Newsletter Sunday finalize: 6:00 PM Sunday (before weekly summary)
    scheduler.add_job(
        func=run_newsletter_sunday_job,
        args=[app],
        trigger=CronTrigger(
            day_of_week='sun',
            hour=18,
            minute=0,
            timezone='America/Chicago'
        ),
        id='newsletter_sunday_finalize',
        name='Newsletter Sunday Finalize',
        replace_existing=True,
        misfire_grace_time=3600
    )

    # ========================================================================
    # Newsletter Jobs (Monthly Dispatch)
    # ========================================================================

    # Newsletter monthly orchestrator: 8:00 AM daily
    # Runs day-of-month-specific actions for the Monthly Dispatch:
    # Day 1: Host DM, coach assignment, QOTM post
    # Day 5: Member highlight request
    # Day 10: Reminders for coach and host
    # Day 12: AI drafts and living post creation
    # Day 13: Final reminders
    # Day 14: Add review buttons
    # Day 15: Manual publish (admin approval)
    scheduler.add_job(
        func=run_newsletter_monthly_orchestrator_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='newsletter_monthly_orchestrator',
        name='Newsletter Monthly Orchestrator',
        replace_existing=True,
        misfire_grace_time=3600  # 1 hour grace
    )

    scheduler.start()

    app.logger.info("=" * 60)
    app.logger.info("APScheduler started successfully")
    app.logger.info("Registered jobs:")
    for job in scheduler.get_jobs():
        app.logger.info(f"  - {job.name}: {job.trigger}")
    app.logger.info("=" * 60)

    # Start Slack Socket Mode if available (for local development)
    try:
        from app.slack.bolt_app import is_socket_mode_available, start_socket_mode
        if is_socket_mode_available():
            start_socket_mode(flask_app=app)  # Pass Flask app for context
            app.logger.info("Slack Socket Mode started for local development")
    except Exception as e:
        app.logger.warning(f"Could not start Socket Mode: {e}")

    return True


def get_scheduler_status() -> dict:
    """Get current scheduler status for admin UI.

    Returns:
        Dict with running status, jobs, and next run times.
    """
    status = {
        'running': scheduler.running,
        'jobs': []
    }

    if scheduler.running:
        for job in scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            }
            status['jobs'].append(job_info)

    return status


def trigger_channel_sync_now(app: Flask) -> None:
    """Manually trigger the channel sync job.

    This can be called from the admin UI for on-demand sync.

    Args:
        app: Flask application instance.
    """
    if not scheduler.running:
        # If scheduler isn't running, just run directly
        run_channel_sync_job(app)
    else:
        # Add a one-time job to run immediately
        scheduler.add_job(
            func=run_channel_sync_job,
            args=[app],
            id='manual_channel_sync',
            name='Manual Channel Sync',
            replace_existing=True
        )


def trigger_skipper_job_now(app: Flask, job_type: str, channel_override: str = None) -> dict:
    """Manually trigger a Skipper job.

    This can be called from the admin UI for on-demand evaluation.

    Args:
        app: Flask application instance.
        job_type: One of 'morning_check', '48h_check', '24h_check',
                  'weekly_summary', 'coach_weekly_summary', 'expire_proposals',
                  'practice_announcements', 'newsletter_daily_update',
                  'newsletter_sunday_finalize', 'newsletter_monthly_orchestrator'
        channel_override: Optional channel name to override default for Slack posts.

    Returns:
        Result dict from the job, or error dict if invalid job_type.
    """
    job_map = {
        'morning_check': run_skipper_morning_check_job,
        '48h_check': run_skipper_48h_check_job,
        '24h_check': run_skipper_24h_check_job,
        'evening_lead_check': run_lead_check_job,
        'morning_lead_check': run_lead_check_job,
        'weekly_summary': run_weekly_summary_job,
        'coach_weekly_summary': run_coach_weekly_summary_job,
        'expire_proposals': run_expire_proposals_job,
        'practice_announcements': run_practice_announcements_job,
        'newsletter_daily_update': run_newsletter_daily_job,
        'newsletter_sunday_finalize': run_newsletter_sunday_job,
        'newsletter_monthly_orchestrator': run_newsletter_monthly_orchestrator_job,
    }

    # Jobs that support channel_override
    jobs_with_channel_override = {
        'morning_check', '48h_check', '24h_check',
        'evening_lead_check', 'morning_lead_check',
        'weekly_summary', 'coach_weekly_summary', 'practice_announcements'
    }

    # Lead check jobs require check_type parameter
    lead_check_types = {
        'evening_lead_check': 'evening',
        'morning_lead_check': 'morning',
    }

    if job_type not in job_map:
        return {'error': f'Unknown job type: {job_type}', 'valid_types': list(job_map.keys())}

    job_func = job_map[job_type]

    # Determine args based on job type
    if job_type in lead_check_types:
        check_type = lead_check_types[job_type]
        job_args = [app, check_type, channel_override] if channel_override else [app, check_type]
    elif job_type in jobs_with_channel_override and channel_override:
        job_args = [app, channel_override]
    else:
        job_args = [app]

    if not scheduler.running:
        # Run directly
        if job_type in jobs_with_channel_override and channel_override:
            job_func(app, channel_override=channel_override)
        else:
            job_func(app)
        return {'status': 'completed', 'job': job_type, 'mode': 'direct', 'channel_override': channel_override}
    else:
        # Schedule as one-time job
        scheduler.add_job(
            func=job_func,
            args=job_args,
            id=f'manual_{job_type}',
            name=f'Manual {job_type}',
            replace_existing=True
        )
        return {'status': 'scheduled', 'job': job_type, 'mode': 'scheduler', 'channel_override': channel_override}
