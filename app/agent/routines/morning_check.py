"""
Daily 7am morning check routine.

Evaluates all practices scheduled for today and posts a recap to #practices-core.
If conditions are unsafe, proposes cancellations with Approve/Reject buttons.
"""

import logging
from datetime import datetime, timedelta

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.practices.service import convert_practice_to_info
from app.agent.decision_engine import (
    evaluate_practice,
    should_propose_cancellation,
    load_skipper_config
)
from app.agent.proposals import create_cancellation_proposal
from app.agent.brain import generate_evaluation_summary

logger = logging.getLogger(__name__)


def run_morning_check(channel_override: str = None) -> dict:
    """
    Run morning check for all practices scheduled today.

    Evaluates each practice, posts a daily recap to #practices-core,
    and proposes cancellations if needed. This function is called by
    the scheduler at 7am daily.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with counts of practices checked, proposals created, etc.
    """
    logger.info("=" * 60)
    logger.info("Starting morning practice check")
    logger.info("=" * 60)

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

    # Get today's date range (midnight to midnight UTC)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Find all scheduled or confirmed practices today
    practices = Practice.query.filter(
        Practice.date >= today_start,
        Practice.date < today_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ])
    ).order_by(Practice.date).all()

    logger.info(f"Found {len(practices)} practices scheduled for today")

    results = {
        'enabled': True,
        'dry_run': dry_run,
        'checked': 0,
        'safe': 0,
        'proposals_created': 0,
        'errors': 0,
        'practices': [],
        'recap_posted': False
    }

    # Collect evaluation data for daily recap
    recap_evaluations = []

    for practice in practices:
        try:
            logger.info(f"\nEvaluating practice {practice.id}: "
                       f"{practice.day_of_week} at {practice.date.strftime('%H:%M')}, "
                       f"{practice.location.name if practice.location else 'No location'}")

            # Evaluate practice conditions
            evaluation = evaluate_practice(practice)

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

            # Convert to PracticeInfo for recap
            practice_info = convert_practice_to_info(practice)

            # Prepare recap data for this practice
            recap_data = {
                'practice': practice_info,
                'evaluation': evaluation,
                'summary': summary,
                'is_go': evaluation.is_go,
                'proposal_id': None
            }

            results['checked'] += 1

            # Check if we should propose cancellation
            if should_propose_cancellation(evaluation):
                logger.warning(f"Creating cancellation proposal for practice {practice.id}")

                if not dry_run:
                    proposal = create_cancellation_proposal(practice, evaluation)
                    practice_result['proposal_id'] = proposal.id
                    practice_result['proposal_expires'] = proposal.expires_at.isoformat()
                    recap_data['proposal_id'] = proposal.id
                    results['proposals_created'] += 1
                else:
                    logger.info("[DRY RUN] Would create cancellation proposal")
                    practice_result['proposal_id'] = 'DRY_RUN'
                    recap_data['proposal_id'] = 'DRY_RUN'
                    results['proposals_created'] += 1

            else:
                logger.info(f"Practice {practice.id} cleared for operation")
                results['safe'] += 1
                practice_result['status'] = 'safe'

            results['practices'].append(practice_result)
            recap_evaluations.append(recap_data)

        except Exception as e:
            logger.error(f"Error evaluating practice {practice.id}: {e}", exc_info=True)
            results['errors'] += 1
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    # Post daily recap to #practices-core (only if there are practices)
    if recap_evaluations and not dry_run:
        try:
            from app.slack.practices import post_daily_practice_recap
            recap_result = post_daily_practice_recap(recap_evaluations, channel_override=channel_override)
            results['recap_posted'] = recap_result.get('success', False)
            results['channel_override'] = channel_override
            if recap_result.get('success'):
                logger.info(f"Daily recap posted (channel_override={channel_override})")
            else:
                logger.error(f"Failed to post daily recap: {recap_result.get('error')}")
        except Exception as e:
            logger.error(f"Error posting daily recap: {e}", exc_info=True)
            results['recap_posted'] = False
    elif dry_run and recap_evaluations:
        logger.info("[DRY RUN] Would post daily recap")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Morning check complete")
    logger.info(f"Practices checked: {results['checked']}")
    logger.info(f"Safe to proceed: {results['safe']}")
    logger.info(f"Cancellations proposed: {results['proposals_created']}")
    logger.info(f"Errors: {results['errors']}")
    logger.info(f"Recap posted: {results['recap_posted']}")
    if dry_run:
        logger.info("DRY RUN - No changes made to database or Slack")
    logger.info("=" * 60)

    return results
