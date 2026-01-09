"""Admin routes for scheduled tasks management.

Provides a UI for manually triggering scheduled jobs with optional
channel override for testing and debugging.
"""

import threading
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app

from app.routes.admin import admin_required

admin_scheduled_tasks = Blueprint('admin_scheduled_tasks', __name__)

# Module-level status tracking for background jobs (similar to channel sync)
_job_status = {
    'running': False,
    'job_id': None,
    'job_name': None,
    'result': None,
    'error': None,
    'started_at': None,
    'completed_at': None,
    'channel_override': None
}

# Known channels for dropdown
KNOWN_CHANNELS = [
    {'id': 'default', 'name': '(Default)', 'description': 'Use job\'s default channel'},
    {'id': 'practices', 'name': '#practices'},
    {'id': 'practices-core', 'name': '#practices-core'},
    {'id': 'collab-coaches-practices', 'name': '#collab-coaches-practices'},
    {'id': 'coord-practices-leads-assists', 'name': '#coord-practices-leads-assists'},
    {'id': 'tcsc-logging', 'name': '#tcsc-logging'},
    {'id': 'general', 'name': '#general'},
]

# Job definitions with metadata
TRIGGERABLE_JOBS = [
    {
        'id': 'morning_check',
        'name': 'Skipper Morning Check',
        'description': 'Evaluates today\'s practices for safety conditions',
        'default_channel': '#practices-core',
        'schedule': 'Daily 7:00am',
        'supports_channel_override': True,
    },
    {
        'id': '48h_check',
        'name': '48h Workout Reminder',
        'description': 'Nudges coaches for workout submission',
        'default_channel': '#collab-coaches-practices',
        'schedule': 'Daily 7:15am',
        'supports_channel_override': True,
    },
    {
        'id': '24h_check',
        'name': '24h Lead Confirmation',
        'description': 'Confirms lead availability for tomorrow',
        'default_channel': '#coord-practices-leads-assists',
        'schedule': 'Daily 7:30am',
        'supports_channel_override': True,
    },
    {
        'id': 'practice_announcements',
        'name': 'Daily Practice Announcements',
        'description': 'Posts practice announcements (8am for evening, 8pm for morning)',
        'default_channel': '#practices',
        'schedule': '8:00am / 8:00pm',
        'supports_channel_override': True,
    },
    {
        'id': 'coach_weekly_summary',
        'name': 'Coach Weekly Review',
        'description': 'Posts weekly summary to coaches with Edit buttons',
        'default_channel': '#collab-coaches-practices',
        'schedule': 'Sundays 4:00pm',
        'supports_channel_override': True,
    },
    {
        'id': 'weekly_summary',
        'name': 'Weekly Practice Summary',
        'description': 'Posts upcoming week overview to members',
        'default_channel': '#practices',
        'schedule': 'Sundays 8:30pm',
        'supports_channel_override': True,
    },
]


def _run_job_background(app, job_id, channel_override=None):
    """Run job in background thread with app context."""
    global _job_status

    with app.app_context():
        try:
            from app.scheduler import trigger_skipper_job_now

            result = trigger_skipper_job_now(app, job_id, channel_override=channel_override)

            _job_status['result'] = result
            _job_status['error'] = None

        except Exception as e:
            current_app.logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            _job_status['error'] = str(e)
            _job_status['result'] = None
        finally:
            _job_status['running'] = False
            _job_status['completed_at'] = datetime.utcnow().isoformat()


@admin_scheduled_tasks.route('/admin/scheduled-tasks')
@admin_required
def index():
    """Render the scheduled tasks dashboard."""
    return render_template('admin/scheduled_tasks.html')


@admin_scheduled_tasks.route('/admin/scheduled-tasks/status')
@admin_required
def get_status():
    """Get scheduler status and job list."""
    from app.scheduler import get_scheduler_status

    scheduler_status = get_scheduler_status()

    # Enrich job metadata with next run times
    jobs_with_status = []
    for job in TRIGGERABLE_JOBS:
        job_info = job.copy()

        # Find next run time from scheduler
        for sched_job in scheduler_status.get('jobs', []):
            if sched_job['id'] == job['id'] or sched_job['id'].endswith(f"_{job['id']}"):
                job_info['next_run'] = sched_job.get('next_run')
                break

        jobs_with_status.append(job_info)

    return jsonify({
        'scheduler': scheduler_status,
        'jobs': jobs_with_status,
        'current_job': {
            'running': _job_status['running'],
            'job_id': _job_status['job_id'],
            'job_name': _job_status['job_name'],
            'started_at': _job_status['started_at']
        }
    })


@admin_scheduled_tasks.route('/admin/scheduled-tasks/channels')
@admin_required
def get_channels():
    """Get list of known channels for dropdown."""
    return jsonify({'channels': KNOWN_CHANNELS})


@admin_scheduled_tasks.route('/admin/scheduled-tasks/trigger/<job_id>', methods=['POST'])
@admin_required
def trigger_job(job_id):
    """Trigger a job to run in the background."""
    global _job_status

    # Check if already running
    if _job_status['running']:
        return jsonify({
            'status': 'already_running',
            'job_id': _job_status['job_id'],
            'job_name': _job_status['job_name']
        }), 409

    # Validate job_id
    job = next((j for j in TRIGGERABLE_JOBS if j['id'] == job_id), None)
    if not job:
        return jsonify({'status': 'error', 'error': f'Unknown job: {job_id}'}), 400

    # Get channel override from request
    data = request.get_json() or {}
    channel_override = data.get('channel_override')
    if channel_override == 'default':
        channel_override = None

    # Mark as running
    _job_status['running'] = True
    _job_status['job_id'] = job_id
    _job_status['job_name'] = job['name']
    _job_status['result'] = None
    _job_status['error'] = None
    _job_status['started_at'] = datetime.utcnow().isoformat()
    _job_status['completed_at'] = None
    _job_status['channel_override'] = channel_override

    # Start background thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_job_background,
        args=(app, job_id, channel_override)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'status': 'started',
        'job_id': job_id,
        'job_name': job['name'],
        'started_at': _job_status['started_at'],
        'channel_override': channel_override
    })


@admin_scheduled_tasks.route('/admin/scheduled-tasks/result')
@admin_required
def get_result():
    """Poll for job result."""
    global _job_status

    if _job_status['running']:
        return jsonify({
            'status': 'running',
            'job_id': _job_status['job_id'],
            'job_name': _job_status['job_name'],
            'started_at': _job_status['started_at']
        })

    if _job_status['error']:
        return jsonify({
            'status': 'error',
            'job_id': _job_status['job_id'],
            'job_name': _job_status['job_name'],
            'error': _job_status['error'],
            'started_at': _job_status['started_at'],
            'completed_at': _job_status['completed_at']
        })

    if _job_status['result']:
        return jsonify({
            'status': 'completed',
            'job_id': _job_status['job_id'],
            'job_name': _job_status['job_name'],
            'result': _job_status['result'],
            'channel_override': _job_status['channel_override'],
            'started_at': _job_status['started_at'],
            'completed_at': _job_status['completed_at']
        })

    return jsonify({'status': 'idle'})
