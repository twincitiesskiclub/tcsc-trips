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
        'category': 'practices',
    },
    {
        'id': '48h_check',
        'name': '48h Workout Reminder',
        'description': 'Nudges coaches for workout submission',
        'default_channel': '#collab-coaches-practices',
        'schedule': 'Daily 7:15am',
        'supports_channel_override': True,
        'category': 'practices',
    },
    {
        'id': '24h_check',
        'name': '24h Lead Confirmation',
        'description': 'Confirms lead availability for tomorrow',
        'default_channel': '#coord-practices-leads-assists',
        'schedule': 'Daily 7:30am',
        'supports_channel_override': True,
        'category': 'practices',
    },
    {
        'id': 'practice_announcements',
        'name': 'Daily Practice Announcements',
        'description': 'Posts practice announcements (8am for evening, 8pm for morning)',
        'default_channel': '#practices',
        'schedule': '8:00am / 8:00pm',
        'supports_channel_override': True,
        'category': 'practices',
    },
    {
        'id': 'coach_weekly_summary',
        'name': 'Coach Weekly Review',
        'description': 'Posts weekly summary to coaches with Edit buttons',
        'default_channel': '#collab-coaches-practices',
        'schedule': 'Sundays 4:00pm',
        'supports_channel_override': True,
        'category': 'practices',
    },
    {
        'id': 'weekly_summary',
        'name': 'Weekly Practice Summary',
        'description': 'Posts upcoming week overview to members',
        'default_channel': '#practices',
        'schedule': 'Sundays 8:30pm',
        'supports_channel_override': True,
        'category': 'practices',
    },
    {
        'id': 'newsletter_daily_update',
        'name': 'Newsletter Daily Update',
        'description': 'Regenerate newsletter with latest content',
        'default_channel': None,
        'schedule': 'Daily 8:00am',
        'supports_channel_override': False,
        'category': 'newsletter',
    },
    {
        'id': 'newsletter_sunday_finalize',
        'name': 'Newsletter Sunday Finalize',
        'description': 'Finalize newsletter and add review buttons',
        'default_channel': None,
        'schedule': 'Sundays 6:00pm',
        'supports_channel_override': False,
        'category': 'newsletter',
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


# =============================================================================
# Newsletter Trigger Endpoints
# =============================================================================

@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/qotm', methods=['POST'])
@admin_required
def trigger_qotm():
    """Trigger QOTM (Question of the Month) post to #chat channel.

    Expects JSON body with optional:
    - question: str (uses newsletter.qotm_question if not provided)
    - channel: str (defaults to 'chat')
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.qotm import post_qotm_to_channel

    data = request.get_json() or {}

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    # Get question from request or newsletter
    question = data.get('question') or newsletter.qotm_question
    if not question:
        return jsonify({
            'success': False,
            'error': 'No question provided and no qotm_question set on newsletter'
        }), 400

    channel = data.get('channel', 'chat')

    result = post_qotm_to_channel(
        newsletter_id=newsletter.id,
        question=question,
        channel=channel
    )

    return jsonify(result)


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/coach', methods=['POST'])
@admin_required
def trigger_coach():
    """Trigger coach assignment and DM.

    Auto-selects the next coach in rotation and sends them a DM
    requesting their Coaches Corner content.

    Expects JSON body with optional:
    - coach_user_id: int (auto-selects if not provided)
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.coach_rotation import assign_coach_for_month, send_coach_request
    from app.models import db

    data = request.get_json() or {}

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    # Assign coach (auto-select if not provided)
    coach_user_id = data.get('coach_user_id')
    assign_result = assign_coach_for_month(
        newsletter_id=newsletter.id,
        coach_user_id=coach_user_id
    )

    if not assign_result.get('success'):
        return jsonify(assign_result)

    # Send request DM to coach
    dm_result = send_coach_request(newsletter_id=newsletter.id)

    return jsonify({
        'success': dm_result.get('success', False),
        'assignment': assign_result,
        'dm': dm_result
    })


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/host', methods=['POST'])
@admin_required
def trigger_host():
    """Trigger host DM to request opener/closer content.

    Requires a host to already be assigned to the newsletter.
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.host import send_host_request
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    result = send_host_request(newsletter_id=newsletter.id)

    return jsonify(result)


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/highlight', methods=['POST'])
@admin_required
def trigger_highlight():
    """Trigger member highlight request DM.

    Requires a member to already be nominated for the highlight.
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.member_highlight import send_highlight_request
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    result = send_highlight_request(newsletter_id=newsletter.id)

    return jsonify(result)


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/ai-drafts', methods=['POST'])
@admin_required
def trigger_ai_drafts():
    """Trigger AI draft generation for newsletter sections.

    Generates AI drafts for sections that need content.
    Note: This is a placeholder - the generate_ai_drafts function
    may need to be implemented in the service module.
    """
    from app.newsletter.models import Newsletter
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    # Try to import generate_ai_drafts if it exists
    try:
        from app.newsletter.service import generate_ai_drafts
        result = generate_ai_drafts(newsletter_id=newsletter.id)
        return jsonify(result)
    except ImportError:
        # Function not yet implemented - return stub response
        current_app.logger.warning("generate_ai_drafts not yet implemented")
        return jsonify({
            'success': False,
            'error': 'generate_ai_drafts function not yet implemented',
            'newsletter_id': newsletter.id
        }), 501


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/living-post', methods=['POST'])
@admin_required
def trigger_living_post():
    """Trigger living post creation or update.

    Creates a new living post if none exists, or updates the existing one.
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.slack_actions import create_living_post, update_living_post
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    # Determine content to post
    content = newsletter.current_content or f"Monthly Dispatch for {newsletter.month_year} - Building..."

    try:
        if not newsletter.slack_main_message_ts:
            # Create new living post
            post_ref = create_living_post(newsletter, content)
            action = 'created'
        else:
            # Update existing post
            post_ref = update_living_post(newsletter, content)
            action = 'updated'

        return jsonify({
            'success': True,
            'action': action,
            'channel_id': post_ref.channel_id if post_ref else None,
            'message_ts': post_ref.message_ts if post_ref else None,
            'newsletter_id': newsletter.id
        })

    except Exception as e:
        current_app.logger.error(f"Error with living post: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'newsletter_id': newsletter.id
        }), 500


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/reminders', methods=['POST'])
@admin_required
def trigger_reminders():
    """Trigger all pending reminders for the current newsletter.

    Sends reminders to:
    - Host (if not submitted)
    - Coach (if not submitted)
    - Member highlight (if nominated but not submitted)
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.host import send_host_reminder
    from app.newsletter.coach_rotation import send_coach_reminder
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    results = {
        'newsletter_id': newsletter.id,
        'reminders_sent': []
    }

    # Send host reminder
    host_result = send_host_reminder(newsletter_id=newsletter.id)
    results['host_reminder'] = host_result
    if host_result.get('success') and not host_result.get('skipped'):
        results['reminders_sent'].append('host')

    # Send coach reminder
    coach_result = send_coach_reminder(newsletter_id=newsletter.id)
    results['coach_reminder'] = coach_result
    if coach_result.get('success') and not coach_result.get('skipped'):
        results['reminders_sent'].append('coach')

    # Note: Member highlight reminders could be added here if needed

    results['success'] = True
    results['total_sent'] = len(results['reminders_sent'])

    return jsonify(results)


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/trigger/photo-thread', methods=['POST'])
@admin_required
def trigger_photo_thread():
    """Trigger photo gallery thread creation.

    Posts selected photos as a thread reply to the published newsletter.
    Requires the newsletter to be published (has publish_message_ts and publish_channel_id).
    """
    from app.newsletter.models import Newsletter
    from app.newsletter.photos import post_photo_gallery_thread
    from app.models import db

    newsletter = Newsletter.get_or_create_current_month()
    if not newsletter:
        return jsonify({'success': False, 'error': 'Could not get or create newsletter'}), 500

    db.session.commit()

    # Check if newsletter has been published
    if not newsletter.publish_message_ts or not newsletter.publish_channel_id:
        return jsonify({
            'success': False,
            'error': 'Newsletter must be published before posting photo gallery thread',
            'newsletter_id': newsletter.id,
            'has_publish_message_ts': bool(newsletter.publish_message_ts),
            'has_publish_channel_id': bool(newsletter.publish_channel_id)
        }), 400

    result = post_photo_gallery_thread(
        newsletter_id=newsletter.id,
        parent_message_ts=newsletter.publish_message_ts,
        channel_id=newsletter.publish_channel_id
    )

    return jsonify(result)


@admin_scheduled_tasks.route('/admin/scheduled-tasks/newsletter/create', methods=['POST'])
@admin_required
def create_newsletter():
    """Create a newsletter for a specific month.

    Expects JSON body with:
    - month_year: str in YYYY-MM format (e.g., "2026-01")
    - qotm_question: str (optional) - Question of the Month
    """
    from app.newsletter.models import Newsletter
    from app.models import db

    data = request.get_json() or {}

    month_year = data.get('month_year')
    if not month_year:
        return jsonify({
            'success': False,
            'error': 'month_year is required (format: YYYY-MM)'
        }), 400

    # Validate format
    try:
        year, month = map(int, month_year.split('-'))
        if not (1 <= month <= 12):
            raise ValueError("Invalid month")
        if year < 2020 or year > 2100:
            raise ValueError("Invalid year")
    except (ValueError, AttributeError) as e:
        return jsonify({
            'success': False,
            'error': f'Invalid month_year format: {e}. Expected YYYY-MM'
        }), 400

    # Get or create newsletter
    newsletter = Newsletter.get_or_create_current_month(month_year)

    # Set QOTM question if provided
    if data.get('qotm_question'):
        newsletter.qotm_question = data['qotm_question']

    db.session.commit()

    return jsonify({
        'success': True,
        'newsletter_id': newsletter.id,
        'month_year': newsletter.month_year,
        'period_start': newsletter.period_start.isoformat() if newsletter.period_start else None,
        'period_end': newsletter.period_end.isoformat() if newsletter.period_end else None,
        'publish_target_date': newsletter.publish_target_date.isoformat() if newsletter.publish_target_date else None,
        'qotm_question': newsletter.qotm_question,
        'status': newsletter.status
    })
