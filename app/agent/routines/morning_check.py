"""
Daily 7am morning check routine.

Evaluates all practices scheduled for today and proposes cancellations
for unsafe conditions. This is the primary Skipper workflow.
"""

import logging
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

logger = logging.getLogger(__name__)


def run_morning_check() -> dict:
    """
    Run morning check for all practices scheduled today.

    Evaluates each practice and proposes cancellations if needed.
    This function is called by the scheduler at 7am daily.

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
        'practices': []
    }

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

            results['checked'] += 1

            # Check if we should propose cancellation
            if should_propose_cancellation(evaluation):
                logger.warning(f"Creating cancellation proposal for practice {practice.id}")

                if not dry_run:
                    proposal = create_cancellation_proposal(practice, evaluation)
                    practice_result['proposal_id'] = proposal.id
                    practice_result['proposal_expires'] = proposal.expires_at.isoformat()
                    results['proposals_created'] += 1
                else:
                    logger.info("[DRY RUN] Would create cancellation proposal")
                    practice_result['proposal_id'] = 'DRY_RUN'
                    results['proposals_created'] += 1

            else:
                logger.info(f"Practice {practice.id} cleared for operation")
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

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Morning check complete")
    logger.info(f"Practices checked: {results['checked']}")
    logger.info(f"Safe to proceed: {results['safe']}")
    logger.info(f"Cancellations proposed: {results['proposals_created']}")
    logger.info(f"Errors: {results['errors']}")
    if dry_run:
        logger.info("DRY RUN - No changes made to database")
    logger.info("=" * 60)

    return results
