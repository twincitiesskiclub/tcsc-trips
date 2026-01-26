"""
Weekly summary routine (Sunday evening).

Posts an overview of upcoming week's practices to Slack with
weather outlook and participation information.
"""

import logging
import yaml
from datetime import timedelta

from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.agent.decision_engine import evaluate_practice, load_skipper_config
from app.integrations.weather import get_weather_for_location
from app.slack.blocks import build_weekly_summary_blocks
from app.slack.client import get_slack_client, get_channel_id_by_name
from app.practices.service import convert_practice_to_info

logger = logging.getLogger(__name__)


def run_weekly_summary(channel_override: str = None) -> dict:
    """
    Generate and post weekly practice summary.

    Called on Sunday evening to give members a preview of the upcoming
    week's practices, weather outlook, and any special notes.

    Args:
        channel_override: Optional channel name to override default for Slack posts

    Returns:
        Summary dict with practice count and preview data
    """
    logger.info("Generating weekly practice summary")

    config = load_skipper_config()
    dry_run = config.get('agent', {}).get('dry_run', True)

    # Get practices for the upcoming week (next 7 days from now)
    # When run on Sunday evening, this captures Mon-Sun of the coming week
    from app.utils import now_central_naive
    now = now_central_naive()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    practices = Practice.query.filter(
        Practice.date >= week_start,
        Practice.date < week_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ])
    ).order_by(Practice.date).all()

    logger.info(f"Found {len(practices)} practices for week of {week_start.strftime('%B %d')}")

    results = {
        'dry_run': dry_run,
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'practice_count': len(practices),
        'practices': []
    }

    # Build practice summaries
    for practice in practices:
        try:
            practice_info = {
                'id': practice.id,
                'day': practice.day_of_week,
                'date': practice.date.isoformat(),
                'time': practice.date.strftime('%I:%M %p'),
                'location': practice.location.name if practice.location else 'TBD',
                'activities': [a.name for a in practice.activities] if practice.activities else [],
                'has_workout': bool(practice.workout_description),
                'has_social': practice.has_social,
                'is_dark': practice.is_dark_practice
            }

            # Get weather outlook (if location has coordinates)
            if practice.location and practice.location.latitude and practice.location.longitude:
                try:
                    weather = get_weather_for_location(
                        lat=practice.location.latitude,
                        lon=practice.location.longitude,
                        target_datetime=practice.date
                    )

                    practice_info['weather_outlook'] = {
                        'temp_f': int(weather.temperature_f),
                        'feels_like_f': int(weather.feels_like_f),
                        'conditions': weather.conditions_summary,
                        'precipitation_chance': int(weather.precipitation_chance)
                    }

                    logger.info(f"Weather for {practice.day_of_week}: "
                               f"{weather.temperature_f:.0f}°F, {weather.conditions_summary}")

                except Exception as e:
                    logger.warning(f"Failed to get weather for practice {practice.id}: {e}")
                    practice_info['weather_outlook'] = None

            # Get RSVP count
            rsvp_count = len([r for r in practice.rsvps if r.status == 'going'])
            practice_info['rsvp_count'] = rsvp_count

            # Get lead info
            if practice.leads:
                leads = [lead.display_name for lead in practice.leads if lead.role == 'lead']
                coaches = [lead.display_name for lead in practice.leads if lead.role == 'coach']

                practice_info['leads'] = leads
                practice_info['coaches'] = coaches

            results['practices'].append(practice_info)

        except Exception as e:
            logger.error(f"Error processing practice {practice.id}: {e}", exc_info=True)
            results['practices'].append({
                'id': practice.id,
                'error': str(e)
            })

    # Generate summary message
    summary_lines = [
        f"Week of {week_start.strftime('%B %d, %Y')}",
        f"{len(practices)} practices scheduled:"
    ]

    for p in results['practices']:
        if 'error' in p:
            continue

        location = p.get('location', 'TBD')
        activities = ", ".join(p.get('activities', []))
        weather = p.get('weather_outlook')

        line = f"• {p['day']} {p['time']} - {location}"
        if activities:
            line += f" ({activities})"
        if weather:
            line += f" - {weather['temp_f']}°F, {weather['conditions']}"

        summary_lines.append(line)

    summary_text = "\n".join(summary_lines)
    results['summary_text'] = summary_text

    logger.info("\nWeekly Summary:\n" + summary_text)

    if not dry_run:
        # Post to Slack #practices channel (or override if specified)
        try:
            # Determine channel - use override if provided
            if channel_override:
                channel_name = channel_override.lstrip('#')
            else:
                # Get announcement channel from config
                config = load_skipper_config()
                channel_name = config.get('escalation', {}).get('announcement_channel', '#practices')
                channel_name = channel_name.lstrip('#')

            channel_id = get_channel_id_by_name(channel_name)

            if channel_id:
                # Convert practices to PracticeInfo dataclasses for Block Kit
                practice_infos = [convert_practice_to_info(p) for p in practices]

                # Build weather_data dict keyed by practice ID
                weather_data = {}
                for p_result in results['practices']:
                    if p_result.get('weather_outlook'):
                        weather_data[p_result['id']] = p_result['weather_outlook']

                blocks = build_weekly_summary_blocks(practice_infos, weather_data=weather_data)

                client = get_slack_client()
                response = client.chat_postMessage(
                    channel=channel_id,
                    blocks=blocks,
                    text="Weekly Practice Summary"
                )

                logger.info(f"Posted weekly summary to #{channel_name} (ts: {response.get('ts')})")
                results['slack_posted'] = True
                results['slack_message_ts'] = response.get('ts')
                results['channel_override'] = channel_override
            else:
                logger.error(f"Could not find channel #{channel_name}")
                results['slack_posted'] = False
                results['slack_error'] = 'Channel not found'
        except Exception as e:
            logger.error(f"Error posting weekly summary to Slack: {e}", exc_info=True)
            results['slack_posted'] = False
            results['slack_error'] = str(e)
    else:
        logger.info("[DRY RUN] Would post weekly summary to Slack")

    logger.info(f"Weekly summary complete: {len(practices)} practices")

    return results
