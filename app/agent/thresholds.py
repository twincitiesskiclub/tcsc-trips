"""
Threshold evaluation logic for practice safety assessment.

Checks weather, trail conditions, lead availability, and daylight
against configurable thresholds from config/skipper.yaml.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.practices.interfaces import (
    WeatherConditions,
    TrailCondition,
    DaylightInfo,
    ThresholdViolation
)
from app.practices.models import Practice

logger = logging.getLogger(__name__)


def check_weather_thresholds(
    weather: WeatherConditions,
    config: dict
) -> list[ThresholdViolation]:
    """
    Check weather conditions against safety thresholds.

    Args:
        weather: Current weather conditions
        config: Threshold configuration from skipper.yaml

    Returns:
        List of ThresholdViolation objects
    """
    violations = []
    thresholds = config.get('thresholds', {}).get('weather', {})

    # Temperature checks (using feels_like for wind chill/heat index)
    min_temp = thresholds.get('min_temperature_f', -10)
    if weather.feels_like_f < min_temp:
        violations.append(ThresholdViolation(
            threshold_name='min_temperature_f',
            threshold_value=float(min_temp),
            actual_value=weather.feels_like_f,
            severity='critical',
            message=f"Feels like temperature ({weather.feels_like_f:.1f}°F) below minimum safe threshold ({min_temp}°F)"
        ))

    max_temp = thresholds.get('max_temperature_f', 95)
    if weather.feels_like_f > max_temp:
        violations.append(ThresholdViolation(
            threshold_name='max_temperature_f',
            threshold_value=float(max_temp),
            actual_value=weather.feels_like_f,
            severity='critical',
            message=f"Feels like temperature ({weather.feels_like_f:.1f}°F) above maximum safe threshold ({max_temp}°F)"
        ))

    # Wind speed check
    max_wind = thresholds.get('max_wind_speed_mph', 30)
    if weather.wind_speed_mph > max_wind:
        violations.append(ThresholdViolation(
            threshold_name='max_wind_speed_mph',
            threshold_value=float(max_wind),
            actual_value=weather.wind_speed_mph,
            severity='warning',
            message=f"Wind speed ({weather.wind_speed_mph:.1f} mph) exceeds safe threshold ({max_wind} mph)"
        ))

    # Wind gust check
    if weather.wind_gust_mph:
        max_gust = thresholds.get('max_wind_gust_mph', 45)
        if weather.wind_gust_mph > max_gust:
            violations.append(ThresholdViolation(
                threshold_name='max_wind_gust_mph',
                threshold_value=float(max_gust),
                actual_value=weather.wind_gust_mph,
                severity='critical',
                message=f"Wind gusts ({weather.wind_gust_mph:.1f} mph) exceed safe threshold ({max_gust} mph)"
            ))

    # Precipitation check
    max_precip = thresholds.get('max_precipitation_chance', 70)
    if weather.precipitation_chance > max_precip:
        violations.append(ThresholdViolation(
            threshold_name='max_precipitation_chance',
            threshold_value=float(max_precip),
            actual_value=weather.precipitation_chance,
            severity='warning',
            message=f"Precipitation chance ({weather.precipitation_chance:.0f}%) exceeds threshold ({max_precip}%)"
        ))

    # Lightning check
    if thresholds.get('lightning_cancels', True) and weather.has_lightning_threat:
        violations.append(ThresholdViolation(
            threshold_name='lightning_cancels',
            threshold_value=1.0,
            actual_value=1.0,
            severity='critical',
            message="Lightning threat detected - automatic cancellation"
        ))

    # Weather alerts
    for alert in weather.alerts:
        severity = 'critical' if alert.severity in ['severe', 'extreme'] else 'warning'
        violations.append(ThresholdViolation(
            threshold_name='weather_alert',
            threshold_value=0.0,
            actual_value=1.0,
            severity=severity,
            message=f"Active weather alert: {alert.event} - {alert.headline}"
        ))

    logger.info(f"Weather check found {len(violations)} violations")
    return violations


def check_trail_thresholds(
    trail: TrailCondition,
    activity_type: str,
    config: dict
) -> list[ThresholdViolation]:
    """
    Check trail conditions against activity requirements.

    Args:
        trail: Current trail conditions
        activity_type: Type of skiing (e.g., "Classic Skiing", "Skate Skiing")
        config: Threshold configuration from skipper.yaml

    Returns:
        List of ThresholdViolation objects
    """
    violations = []
    thresholds = config.get('thresholds', {}).get('trails', {})

    # Quality levels in order: excellent > good > fair > poor > b_skis > rock_skis
    quality_order = ['excellent', 'good', 'fair', 'poor', 'b_skis', 'rock_skis']

    # Minimum quality check
    min_quality = thresholds.get('min_quality', 'fair')
    if min_quality in quality_order and trail.ski_quality in quality_order:
        min_index = quality_order.index(min_quality)
        actual_index = quality_order.index(trail.ski_quality)

        if actual_index > min_index:
            violations.append(ThresholdViolation(
                threshold_name='min_trail_quality',
                threshold_value=float(min_index),
                actual_value=float(actual_index),
                severity='critical',
                message=f"Trail quality ({trail.ski_quality}) below minimum safe standard ({min_quality})"
            ))

    # Grooming check for skate skiing
    is_skate = 'skate' in activity_type.lower()
    if is_skate and thresholds.get('require_groomed', False):
        if not trail.groomed:
            violations.append(ThresholdViolation(
                threshold_name='require_groomed_skate',
                threshold_value=1.0,
                actual_value=0.0,
                severity='critical',
                message="Skate skiing requires groomed trails"
            ))
        elif trail.groomed_for and trail.groomed_for not in ['skate', 'both']:
            violations.append(ThresholdViolation(
                threshold_name='groomed_for_skate',
                threshold_value=1.0,
                actual_value=0.0,
                severity='warning',
                message=f"Trails groomed for {trail.groomed_for}, not skate skiing"
            ))

    # Trail status check
    if trail.trails_open == 'closed':
        violations.append(ThresholdViolation(
            threshold_name='trails_open',
            threshold_value=1.0,
            actual_value=0.0,
            severity='critical',
            message="Trails reported as closed"
        ))
    elif trail.trails_open == 'partial':
        violations.append(ThresholdViolation(
            threshold_name='trails_open',
            threshold_value=1.0,
            actual_value=0.5,
            severity='warning',
            message="Only partial trail access available"
        ))

    logger.info(f"Trail check found {len(violations)} violations")
    return violations


def check_lead_availability(practice: Practice, config: dict) -> list[ThresholdViolation]:
    """
    Check if practice has confirmed lead within required timeframe.

    Args:
        practice: Practice to check
        config: Threshold configuration from skipper.yaml

    Returns:
        List of ThresholdViolation objects
    """
    violations = []
    thresholds = config.get('thresholds', {}).get('lead', {})

    # Check if lead confirmation is required
    if not thresholds.get('require_confirmed_lead', True):
        return violations

    # Check if practice has any leads assigned
    if not practice.leads:
        violations.append(ThresholdViolation(
            threshold_name='has_lead',
            threshold_value=1.0,
            actual_value=0.0,
            severity='critical',
            message="No practice lead assigned"
        ))
        return violations

    # Check for confirmed leads
    confirmed_leads = [lead for lead in practice.leads if lead.confirmed]

    if not confirmed_leads:
        # Check if we're within confirmation deadline
        deadline_hours = thresholds.get('lead_confirmation_deadline_hours', 24)
        time_until_practice = (practice.date - datetime.utcnow()).total_seconds() / 3600

        if time_until_practice <= deadline_hours:
            violations.append(ThresholdViolation(
                threshold_name='lead_confirmed',
                threshold_value=1.0,
                actual_value=0.0,
                severity='critical',
                message=f"No confirmed lead within {deadline_hours}h of practice"
            ))
        else:
            violations.append(ThresholdViolation(
                threshold_name='lead_confirmed',
                threshold_value=1.0,
                actual_value=0.0,
                severity='warning',
                message="Practice lead has not confirmed yet"
            ))

    logger.info(f"Lead check found {len(violations)} violations")
    return violations


def check_daylight(
    practice: Practice,
    daylight: DaylightInfo,
    config: dict
) -> list[ThresholdViolation]:
    """
    Check if practice requires lights and if conditions are safe.

    Args:
        practice: Practice to check
        daylight: Daylight information for practice date
        config: Threshold configuration from skipper.yaml

    Returns:
        List of ThresholdViolation objects
    """
    violations = []

    # Check if practice is after dark but not marked as dark practice
    if practice.date >= daylight.civil_twilight_end:
        if not practice.is_dark_practice:
            violations.append(ThresholdViolation(
                threshold_name='requires_lights',
                threshold_value=1.0,
                actual_value=0.0,
                severity='warning',
                message=f"Practice after dark (twilight ends {daylight.civil_twilight_end.strftime('%H:%M')}), lights required"
            ))

    # If it's a dark practice, check if location supports it
    # (This would require location metadata about lighting availability)
    # For now, we just flag it for awareness
    if practice.is_dark_practice:
        logger.info("Dark practice scheduled - assuming location has adequate lighting")

    logger.info(f"Daylight check found {len(violations)} violations")
    return violations
