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
- 7:00 AM: Skipper morning check (today's practices) → posts recap to #practices-core
- 7:15 AM: Skipper 48h check (workout reminders) → posts to #collab-coaches-practices
- 7:30 AM: Skipper 24h check (lead confirmation) → posts to #coord-practices-leads-assists
- 8:00 AM: Newsletter daily update → regenerates living post
- 4:00 PM Sunday: Coach weekly review summary (collab-coaches-practices)
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


def run_practice_announcements_job(app: Flask, channel_override: str = None):
    """Execute the daily practice announcement job within app context.

    Posts practice announcements with smart timing:
    - Evening practices (12pm+): Run at 8am, announce same day
    - Morning practices (before 12pm): Run at 8pm, announce for tomorrow

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default for Slack posts.
    """
    from datetime import timedelta

    with app.app_context():
        from app.practices.models import Practice
        from app.practices.interfaces import PracticeStatus
        from app.slack.practices import post_practice_announcement

        app.logger.info("=" * 60)
        app.logger.info("Starting practice announcements job")
        if channel_override:
            app.logger.info(f"Channel override: {channel_override}")
        app.logger.info("=" * 60)

        now = datetime.now()
        practices_to_announce = []

        try:
            if now.hour < 12:
                # Morning run (around 8am): Announce evening practices for today
                today_start = now.replace(hour=12, minute=0, second=0, microsecond=0)
                today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

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

            # Announce each practice
            announced = 0
            errors = 0

            for practice in practices_to_announce:
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

    # 24h check: Confirm leads and weather at 7:30 AM
    scheduler.add_job(
        func=run_skipper_24h_check_job,
        args=[app],
        trigger=CronTrigger(
            hour=7,
            minute=30,
            timezone='America/Chicago'
        ),
        id='skipper_24h_check',
        name='Skipper 24h Check',
        replace_existing=True,
        misfire_grace_time=1800
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

    # Coach weekly review: Post to collab-coaches-practices on Sunday at 4:00 PM
    scheduler.add_job(
        func=run_coach_weekly_summary_job,
        args=[app],
        trigger=CronTrigger(
            day_of_week='sun',
            hour=16,
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
                  'newsletter_sunday_finalize'
        channel_override: Optional channel name to override default for Slack posts.

    Returns:
        Result dict from the job, or error dict if invalid job_type.
    """
    job_map = {
        'morning_check': run_skipper_morning_check_job,
        '48h_check': run_skipper_48h_check_job,
        '24h_check': run_skipper_24h_check_job,
        'weekly_summary': run_weekly_summary_job,
        'coach_weekly_summary': run_coach_weekly_summary_job,
        'expire_proposals': run_expire_proposals_job,
        'practice_announcements': run_practice_announcements_job,
        'newsletter_daily_update': run_newsletter_daily_job,
        'newsletter_sunday_finalize': run_newsletter_sunday_job,
    }

    # Jobs that support channel_override
    jobs_with_channel_override = {
        'morning_check', '48h_check', '24h_check',
        'weekly_summary', 'coach_weekly_summary', 'practice_announcements'
    }

    if job_type not in job_map:
        return {'error': f'Unknown job type: {job_type}', 'valid_types': list(job_map.keys())}

    job_func = job_map[job_type]

    # Determine args based on whether job supports channel_override
    if job_type in jobs_with_channel_override and channel_override:
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
