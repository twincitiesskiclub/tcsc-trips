"""
Lead verification checks for practices.

Two scheduled checks:
- 4pm: Evening practices (noon to midnight today) - includes lead verification
- 10pm: Morning practices (before noon tomorrow) - includes lead verification

Both checks post to #practices-core if issues are found (weather, conditions, OR lead).
Additionally sends a group DM to practices directors + lead if lead hasn't confirmed.
"""

import logging
import pytz
from datetime import datetime, timedelta

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.agent.decision_engine import (
    evaluate_practice,
    should_propose_cancellation,
    load_skipper_config
)
from app.agent.proposals import create_cancellation_proposal
from app.agent.brain import generate_evaluation_summary
from app.utils import CENTRAL_TZ

logger = logging.getLogger(__name__)


def run_evening_lead_check(channel_override: str = None) -> dict:
    """
    Run 4pm check for evening practices (noon to midnight today).

    Evaluates weather, conditions, calendar, AND lead confirmation.
    Posts to #practices-core only if something is wrong.
    Sends group DM if lead hasn't confirmed.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with counts of practices checked, proposals created, etc.
    """
    logger.info("=" * 60)
    logger.info("Starting 4pm evening lead verification check")
    logger.info("=" * 60)

    # Calculate time range: noon to midnight Central time TODAY
    now_central = datetime.now(CENTRAL_TZ)
    noon_central = now_central.replace(hour=12, minute=0, second=0, microsecond=0)
    midnight_central = now_central.replace(hour=23, minute=59, second=59, microsecond=0)

    # Convert to UTC for database query (Practice.date is naive UTC)
    noon_utc = noon_central.astimezone(pytz.UTC).replace(tzinfo=None)
    midnight_utc = midnight_central.astimezone(pytz.UTC).replace(tzinfo=None)

    logger.info(f"Checking practices from {noon_central.strftime('%I:%M %p')} to midnight Central")
    logger.info(f"UTC range: {noon_utc.isoformat()} to {midnight_utc.isoformat()}")

    return _run_lead_verification_check(
        start_utc=noon_utc,
        end_utc=midnight_utc,
        check_name="evening",
        channel_override=channel_override
    )


def run_morning_lead_check(channel_override: str = None) -> dict:
    """
    Run 10pm check for morning practices (before noon tomorrow).

    Evaluates weather, conditions, calendar, AND lead confirmation.
    Posts to #practices-core only if something is wrong.
    Sends group DM if lead hasn't confirmed.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with counts of practices checked, proposals created, etc.
    """
    logger.info("=" * 60)
    logger.info("Starting 10pm morning lead verification check")
    logger.info("=" * 60)

    # Calculate time range: midnight to noon Central time TOMORROW
    now_central = datetime.now(CENTRAL_TZ)
    tomorrow_central = now_central + timedelta(days=1)
    midnight_central = tomorrow_central.replace(hour=0, minute=0, second=0, microsecond=0)
    noon_central = tomorrow_central.replace(hour=12, minute=0, second=0, microsecond=0)

    # Convert to UTC for database query (Practice.date is naive UTC)
    midnight_utc = midnight_central.astimezone(pytz.UTC).replace(tzinfo=None)
    noon_utc = noon_central.astimezone(pytz.UTC).replace(tzinfo=None)

    logger.info(f"Checking practices from midnight to {noon_central.strftime('%I:%M %p')} Central tomorrow")
    logger.info(f"UTC range: {midnight_utc.isoformat()} to {noon_utc.isoformat()}")

    return _run_lead_verification_check(
        start_utc=midnight_utc,
        end_utc=noon_utc,
        check_name="morning",
        channel_override=channel_override
    )


def _run_lead_verification_check(
    start_utc: datetime,
    end_utc: datetime,
    check_name: str,
    channel_override: str = None
) -> dict:
    """
    Core logic for lead verification checks.

    Only posts to #practices-core if there are issues (silent if all good).

    Args:
        start_utc: Start of time range (naive UTC datetime)
        end_utc: End of time range (naive UTC datetime)
        check_name: Name for logging ("evening" or "morning")
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with results
    """
    config = load_skipper_config()

    # Check if agent is enabled
    if not config.get('agent', {}).get('enabled', True):
        logger.info("Skipper agent is disabled in config")
        return {
            'enabled': False,
            'message': 'Agent disabled in config'
        }

    dry_run = config.get('agent', {}).get('dry_run', True)
    if dry_run:
        logger.info("DRY RUN MODE - No database changes will be made")

    # Find practices in the time range
    practices = Practice.query.filter(
        Practice.date >= start_utc,
        Practice.date < end_utc,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ])
    ).order_by(Practice.date).all()

    logger.info(f"Found {len(practices)} {check_name} practices to check")

    results = {
        'enabled': True,
        'dry_run': dry_run,
        'check_name': check_name,
        'checked': 0,
        'safe': 0,
        'proposals_created': 0,
        'dms_sent': 0,
        'errors': 0,
        'practices': []
    }

    # Track practices that need lead DMs
    practices_needing_dm = []

    for practice in practices:
        try:
            logger.info(f"\nEvaluating practice {practice.id}: "
                       f"{practice.day_of_week} at {practice.date.strftime('%H:%M')}, "
                       f"{practice.location.name if practice.location else 'No location'}")

            # Evaluate practice conditions (INCLUDING lead check)
            evaluation = evaluate_practice(practice, skip_lead_check=False)

            # Generate summary
            summary = generate_evaluation_summary(evaluation)

            logger.info(f"Evaluation: {summary}")
            logger.info(f"Go/No-Go: {'GO' if evaluation.is_go else 'NO-GO'} "
                       f"({len(evaluation.violations)} violations, "
                       f"{evaluation.confidence:.0%} confidence)")

            practice_result = {
                'id': practice.id,
                'date': practice.date.isoformat(),
                'location': practice.location.name if practice.location else None,
                'is_go': evaluation.is_go,
                'violations': len(evaluation.violations),
                'summary': summary
            }

            results['checked'] += 1

            # Check if there are lead-related violations (for DM)
            has_lead_violation = any(
                v.threshold_name in ('has_lead', 'lead_confirmed')
                for v in evaluation.violations
            )
            if has_lead_violation:
                practices_needing_dm.append(practice)

            # Check if we should propose cancellation (any critical violation)
            if should_propose_cancellation(evaluation):
                logger.warning(f"Creating cancellation proposal for practice {practice.id}")

                if not dry_run:
                    proposal = create_cancellation_proposal(
                        practice,
                        evaluation,
                        channel_override=channel_override
                    )
                    practice_result['proposal_id'] = proposal.id
                    practice_result['proposal_expires'] = proposal.expires_at.isoformat()
                    results['proposals_created'] += 1
                else:
                    logger.info("[DRY RUN] Would create cancellation proposal")
                    practice_result['proposal_id'] = 'DRY_RUN'
                    results['proposals_created'] += 1

            else:
                logger.info(f"Practice {practice.id} cleared - no action needed")
                results['safe'] += 1
                practice_result['status'] = 'safe'

            results['practices'].append(practice_result)

        except Exception as e:
            logger.error(f"Error evaluating practice {practice.id}: {e}", exc_info=True)
            results['errors'] += 1
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    # Send group DMs for lead-related issues
    if practices_needing_dm and not dry_run:
        for practice in practices_needing_dm:
            try:
                # Check if we've already sent a nudge today
                if practice.lead_nudge_sent_at:
                    nudge_date = practice.lead_nudge_sent_at.date()
                    today = datetime.utcnow().date()
                    if nudge_date == today:
                        logger.info(f"Already sent DM for practice {practice.id} today, skipping")
                        continue

                from app.slack.practices import send_lead_checkin_dm
                dm_result = send_lead_checkin_dm(practice)
                if dm_result.get('success'):
                    results['dms_sent'] += 1
                    # Mark that we sent the nudge
                    practice.lead_nudge_sent_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"Sent lead check-in DM for practice {practice.id}")
                else:
                    logger.error(f"Failed to send DM for practice {practice.id}: {dm_result.get('error')}")
            except Exception as e:
                logger.error(f"Error sending DM for practice {practice.id}: {e}", exc_info=True)
    elif dry_run and practices_needing_dm:
        logger.info(f"[DRY RUN] Would send {len(practices_needing_dm)} lead check-in DMs")

    # Summary (silent if all good - no recap post unless there are issues)
    logger.info("\n" + "=" * 60)
    logger.info(f"{check_name.title()} lead verification check complete")
    logger.info(f"Practices checked: {results['checked']}")
    logger.info(f"All clear: {results['safe']}")
    logger.info(f"Cancellations proposed: {results['proposals_created']}")
    logger.info(f"Lead DMs sent: {results['dms_sent']}")
    logger.info(f"Errors: {results['errors']}")
    if dry_run:
        logger.info("DRY RUN - No changes made to database or Slack")
    logger.info("=" * 60)

    return results
