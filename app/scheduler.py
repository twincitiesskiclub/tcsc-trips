"""APScheduler setup for background jobs.

This module sets up a background scheduler that runs within the existing
web process (no separate worker needed). Jobs run in a thread pool while
web requests are handled normally.

Safety:
- Single-worker guard prevents duplicate job execution with Gunicorn
- Jobs are scheduled to run at 3am Central time (low traffic period)
- All jobs respect dry_run config by default
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

    scheduler.start()

    app.logger.info("=" * 60)
    app.logger.info("APScheduler started successfully")
    app.logger.info("Registered jobs:")
    for job in scheduler.get_jobs():
        app.logger.info(f"  - {job.name}: {job.trigger}")
    app.logger.info("=" * 60)

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
