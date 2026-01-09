"""
Pre-practice check routines (48h and 24h before practice).

48h check: Post workout reminder to #collab-coaches-practices (tag @kj)
24h check: Post lead confirmation to #coord-practices-leads-assists (tag leads)
"""

import logging
from datetime import datetime, timedelta

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.agent.decision_engine import evaluate_practice, load_skipper_config
from app.agent.brain import generate_evaluation_summary
from app.slack.practices import (
    post_48h_workout_reminder,
    post_24h_lead_confirmation,
    update_practice_announcement
)

logger = logging.getLogger(__name__)


def run_48h_check(channel_override: str = None) -> dict:
    """
    Check practices 48 hours out and post reminder to #collab-coaches-practices.

    This routine helps ensure workouts are posted with enough time for
    members to see them and plan their participation. Tags @kj as a safety check.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with results
    """
    logger.info("Running 48-hour pre-practice check")

    config = load_skipper_config()
    dry_run = config.get('agent', {}).get('dry_run', True)

    # Calculate 48-hour window (between 46-50 hours from now)
    now = datetime.utcnow()
    window_start = now + timedelta(hours=46)
    window_end = now + timedelta(hours=50)

    practices = Practice.query.filter(
        Practice.date >= window_start,
        Practice.date < window_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ])
    ).all()

    logger.info(f"Found {len(practices)} practices in 48h window")

    results = {
        'dry_run': dry_run,
        'checked': 0,
        'needs_workout': 0,
        'has_workout': 0,
        'channel_post_sent': False,
        'practices': []
    }

    # Collect practices needing workouts
    practices_needing_workout = []

    for practice in practices:
        try:
            logger.info(f"Checking practice {practice.id}: {practice.date}")

            practice_result = {
                'id': practice.id,
                'date': practice.date.isoformat(),
                'has_workout': bool(practice.workout_description),
                'has_leads': len(practice.leads) > 0
            }

            results['checked'] += 1

            # Check if workout is posted
            if practice.workout_description:
                logger.info(f"Practice {practice.id} has workout posted")
                results['has_workout'] += 1
                practice_result['status'] = 'workout_ready'
            else:
                logger.info(f"Practice {practice.id} needs workout submission")
                results['needs_workout'] += 1
                practice_result['status'] = 'needs_workout'
                practices_needing_workout.append(practice)

            results['practices'].append(practice_result)

        except Exception as e:
            logger.error(f"Error checking practice {practice.id}: {e}", exc_info=True)
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    # Post channel reminder if any practices need workouts
    if practices_needing_workout:
        if not dry_run:
            try:
                post_result = post_48h_workout_reminder(practices_needing_workout, channel_override=channel_override)
                results['channel_post_sent'] = post_result.get('success', False)
                results['channel_override'] = channel_override
                if post_result.get('success'):
                    logger.info(f"Posted 48h workout reminder (channel_override={channel_override})")
                else:
                    logger.error(f"Failed to post 48h reminder: {post_result.get('error')}")
            except Exception as e:
                logger.error(f"Error posting 48h reminder: {e}", exc_info=True)
        else:
            logger.info(f"[DRY RUN] Would post reminder for {len(practices_needing_workout)} practices")

    logger.info(f"48h check complete: {results['checked']} checked, "
               f"{results['needs_workout']} need workouts, "
               f"channel_post_sent={results['channel_post_sent']}")

    return results


def run_24h_check(channel_override: str = None) -> dict:
    """
    Check practices 24 hours out and post lead confirmation request to
    #coord-practices-leads-assists.

    Also provides weather updates to practice announcements if conditions
    have changed significantly.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with confirmation status and weather updates
    """
    logger.info("Running 24-hour pre-practice check")

    config = load_skipper_config()
    dry_run = config.get('agent', {}).get('dry_run', True)

    # Calculate 24-hour window (between 22-26 hours from now)
    now = datetime.utcnow()
    window_start = now + timedelta(hours=22)
    window_end = now + timedelta(hours=26)

    practices = Practice.query.filter(
        Practice.date >= window_start,
        Practice.date < window_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ])
    ).all()

    logger.info(f"Found {len(practices)} practices in 24h window")

    results = {
        'dry_run': dry_run,
        'checked': 0,
        'confirmed': 0,
        'needs_confirmation': 0,
        'weather_updates': 0,
        'channel_post_sent': False,
        'practices': []
    }

    # Collect practices needing lead confirmation with their lead Slack IDs
    practices_needing_confirmation = []

    for practice in practices:
        try:
            logger.info(f"Checking practice {practice.id}: {practice.date}")

            # Evaluate current conditions
            evaluation = evaluate_practice(practice)
            summary = generate_evaluation_summary(evaluation)

            practice_result = {
                'id': practice.id,
                'date': practice.date.isoformat(),
                'has_confirmed_lead': evaluation.has_confirmed_lead,
                'is_go': evaluation.is_go,
                'summary': summary
            }

            results['checked'] += 1

            # Check lead confirmation
            if evaluation.has_confirmed_lead:
                logger.info(f"Practice {practice.id} has confirmed lead")
                results['confirmed'] += 1
                practice_result['lead_status'] = 'confirmed'
            else:
                logger.warning(f"Practice {practice.id} needs lead confirmation")
                results['needs_confirmation'] += 1
                practice_result['lead_status'] = 'needs_confirmation'

                # Identify leads to contact
                leads = [lead for lead in practice.leads if lead.role == 'lead']
                if leads:
                    lead_slack_ids = []
                    for lead in leads:
                        slack_uid = lead.user.slack_user.slack_uid if lead.user and lead.user.slack_user else None
                        if slack_uid:
                            lead_slack_ids.append(slack_uid)

                    if lead_slack_ids:
                        practices_needing_confirmation.append((practice, lead_slack_ids))
                    practice_result['leads_to_contact'] = [lead.display_name for lead in leads]

            # Weather update
            if evaluation.weather:
                logger.info(f"Weather: {evaluation.weather.conditions_summary}, "
                           f"{evaluation.weather.temperature_f:.0f}°F "
                           f"(feels like {evaluation.weather.feels_like_f:.0f}°F)")

                practice_result['weather'] = {
                    'temp_f': evaluation.weather.temperature_f,
                    'feels_like_f': evaluation.weather.feels_like_f,
                    'conditions': evaluation.weather.conditions_summary,
                    'wind_mph': evaluation.weather.wind_speed_mph
                }

                # Check if conditions warrant an update
                if evaluation.violations:
                    logger.info(f"Weather update needed: {len(evaluation.violations)} issues")
                    results['weather_updates'] += 1
                    practice_result['send_weather_update'] = True

                    if not dry_run:
                        # Post weather update to Slack practice announcement
                        try:
                            result = update_practice_announcement(
                                practice,
                                weather=evaluation.weather,
                                trail_conditions=evaluation.trail_conditions
                            )
                            if result['success']:
                                logger.info(f"Posted weather update for practice #{practice.id}")
                            else:
                                logger.warning(f"Failed to update announcement: {result.get('error')}")
                        except Exception as e:
                            logger.error(f"Error posting weather update: {e}", exc_info=True)
                    else:
                        logger.info("[DRY RUN] Would post weather update")

            results['practices'].append(practice_result)

        except Exception as e:
            logger.error(f"Error checking practice {practice.id}: {e}", exc_info=True)
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    # Post channel confirmation request if any practices need it
    if practices_needing_confirmation:
        if not dry_run:
            try:
                post_result = post_24h_lead_confirmation(practices_needing_confirmation, channel_override=channel_override)
                results['channel_post_sent'] = post_result.get('success', False)
                results['channel_override'] = channel_override
                if post_result.get('success'):
                    logger.info(f"Posted 24h lead confirmation (channel_override={channel_override})")
                else:
                    logger.error(f"Failed to post 24h confirmation: {post_result.get('error')}")
            except Exception as e:
                logger.error(f"Error posting 24h confirmation: {e}", exc_info=True)
        else:
            logger.info(f"[DRY RUN] Would post confirmation for {len(practices_needing_confirmation)} practices")

    logger.info(f"24h check complete: {results['checked']} checked, "
               f"{results['confirmed']} confirmed leads, "
               f"{results['weather_updates']} weather updates, "
               f"channel_post_sent={results['channel_post_sent']}")

    return results
