"""
Pre-practice check routines (48h and 24h before practice).

48h check: Nudge coaches to submit workout plan
24h check: Confirm lead availability and provide weather update
"""

import logging
from datetime import datetime, timedelta

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.agent.decision_engine import evaluate_practice, load_skipper_config
from app.agent.brain import generate_evaluation_summary
from app.slack.practices import (
    send_workout_reminder,
    send_lead_availability_request,
    update_practice_announcement
)

logger = logging.getLogger(__name__)


def run_48h_check() -> dict:
    """
    Check practices 48 hours out and nudge coaches for workout submission.

    This routine helps ensure workouts are posted with enough time for
    members to see them and plan their participation.

    Returns:
        Summary dict with nudge counts and results
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
        'nudges_sent': 0,
        'practices': []
    }

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

                # Identify coaches to nudge
                coaches = [lead for lead in practice.leads if lead.role == 'coach']

                if coaches:
                    logger.info(f"Nudging {len(coaches)} coach(es) for workout")
                    practice_result['coaches_to_nudge'] = [
                        lead.person.short_name for lead in coaches
                    ]

                    if not dry_run:
                        # Send Slack DM to coaches
                        for coach in coaches:
                            if coach.person.slack_user_id:
                                try:
                                    result = send_workout_reminder(practice, coach.person.slack_user_id)
                                    if result['success']:
                                        results['nudges_sent'] += 1
                                    else:
                                        logger.warning(f"Failed to send reminder to {coach.person.short_name}: {result.get('error')}")
                                except Exception as e:
                                    logger.error(f"Error sending reminder to {coach.person.short_name}: {e}", exc_info=True)
                            else:
                                logger.warning(f"Coach {coach.person.short_name} has no Slack user ID")
                    else:
                        logger.info(f"[DRY RUN] Would nudge coaches: {practice_result['coaches_to_nudge']}")
                        results['nudges_sent'] += len(coaches)
                else:
                    logger.warning(f"Practice {practice.id} has no coach assigned")
                    practice_result['issue'] = 'no_coach'

            results['practices'].append(practice_result)

        except Exception as e:
            logger.error(f"Error checking practice {practice.id}: {e}", exc_info=True)
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    logger.info(f"48h check complete: {results['checked']} checked, "
               f"{results['needs_workout']} need workouts, "
               f"{results['nudges_sent']} nudges sent")

    return results


def run_24h_check() -> dict:
    """
    Check practices 24 hours out for lead confirmation and weather update.

    Provides final go/no-go assessment and alerts leads if conditions
    have changed significantly since the 48h check.

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
        'practices': []
    }

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
                    practice_result['leads_to_contact'] = [
                        lead.person.short_name for lead in leads
                    ]

                    if not dry_run:
                        # Send Slack DM to leads
                        for lead in leads:
                            if lead.person.slack_user_id:
                                try:
                                    result = send_lead_availability_request(practice, lead.person.slack_user_id)
                                    if result['success']:
                                        logger.info(f"Sent confirmation request to {lead.person.short_name}")
                                    else:
                                        logger.warning(f"Failed to send confirmation to {lead.person.short_name}: {result.get('error')}")
                                except Exception as e:
                                    logger.error(f"Error sending confirmation to {lead.person.short_name}: {e}", exc_info=True)
                            else:
                                logger.warning(f"Lead {lead.person.short_name} has no Slack user ID")
                    else:
                        logger.info(f"[DRY RUN] Would contact leads: {practice_result['leads_to_contact']}")

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

    logger.info(f"24h check complete: {results['checked']} checked, "
               f"{results['confirmed']} confirmed leads, "
               f"{results['weather_updates']} weather updates sent")

    return results
