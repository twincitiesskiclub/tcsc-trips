"""
Main decision engine for practice evaluation.

Orchestrates data fetching from weather, trail, and daylight APIs,
runs threshold checks, and produces PracticeEvaluation results.
"""

import logging
import os
import yaml
from datetime import datetime
from typing import Optional

from app.practices.interfaces import (
    PracticeEvaluation,
    WeatherConditions,
    TrailCondition,
    DaylightInfo
)
from app.practices.models import Practice
from app.integrations.weather import get_weather_for_location
from app.integrations.trail_conditions import get_trail_conditions
from app.integrations.daylight import get_daylight_info
from app.integrations.event_conflicts import get_event_conflicts
from app.integrations.air_quality import get_air_quality
from app.agent.thresholds import (
    check_weather_thresholds,
    check_trail_thresholds,
    check_lead_availability,
    check_daylight,
    check_event_conflicts,
    check_air_quality
)

logger = logging.getLogger(__name__)

# Module-level config cache
_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None


def load_skipper_config(force_reload: bool = False) -> dict:
    """Load Skipper configuration from YAML file with caching.

    Args:
        force_reload: If True, bypass cache and reload from disk

    Returns:
        Configuration dictionary
    """
    global _config_cache, _config_mtime

    # Get absolute path to config file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, 'config', 'skipper.yaml')

    try:
        # Check if file has been modified since last load
        current_mtime = os.path.getmtime(config_path)

        if not force_reload and _config_cache is not None and _config_mtime == current_mtime:
            return _config_cache

        with open(config_path, 'r') as f:
            _config_cache = yaml.safe_load(f)
            _config_mtime = current_mtime
            logger.debug(f"Loaded skipper config from {config_path}")
            return _config_cache

    except Exception as e:
        logger.error(f"Failed to load skipper.yaml: {e}")
        # Return minimal default config
        return {
            'agent': {'enabled': True, 'dry_run': True},
            'thresholds': {}
        }


def evaluate_practice(
    practice: Practice,
    skip_lead_check: bool = False
) -> PracticeEvaluation:
    """
    Evaluate all conditions for a practice and determine if it's safe to proceed.

    Fetches:
    - Weather conditions from NWS API
    - Trail conditions from SkinnySkI
    - Daylight information for location/date

    Checks:
    - Weather thresholds (temp, wind, precipitation, lightning)
    - Trail quality and grooming for activity type
    - Lead confirmation status (unless skip_lead_check=True)
    - Daylight requirements

    Args:
        practice: Practice to evaluate
        skip_lead_check: If True, skip lead verification (for 7am weather-only check)

    Returns:
        PracticeEvaluation with all violations and go/no-go decision
    """
    logger.info(f"Evaluating practice {practice.id} on {practice.date}")

    config = load_skipper_config()
    evaluation = PracticeEvaluation(
        practice_id=practice.id,
        evaluated_at=datetime.utcnow()
    )

    # Fetch weather conditions
    weather: Optional[WeatherConditions] = None
    if practice.location and practice.location.latitude and practice.location.longitude:
        try:
            weather = get_weather_for_location(
                lat=practice.location.latitude,
                lon=practice.location.longitude,
                target_datetime=practice.date
            )
            evaluation.weather = weather
            logger.info(f"Weather: {weather.temperature_f:.1f}°F, feels like {weather.feels_like_f:.1f}°F, "
                       f"{weather.conditions_summary}")
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            # Continue evaluation without weather data

    # Fetch trail conditions
    trail: Optional[TrailCondition] = None
    if practice.location:
        try:
            trail = get_trail_conditions(practice.location.name)
            evaluation.trail_conditions = trail
            if trail:
                logger.info(f"Trail: {trail.ski_quality}, {trail.trails_open}, "
                           f"groomed: {trail.groomed} ({trail.groomed_for or 'N/A'})")
            else:
                logger.warning(f"No trail report found for {practice.location.name}")
        except Exception as e:
            logger.error(f"Failed to fetch trail conditions: {e}")
            # Continue evaluation without trail data

    # Fetch daylight information
    daylight: Optional[DaylightInfo] = None
    if practice.location and practice.location.latitude and practice.location.longitude:
        try:
            daylight = get_daylight_info(
                lat=practice.location.latitude,
                lon=practice.location.longitude,
                date=practice.date
            )
            logger.info(f"Daylight: sunset {daylight.sunset.strftime('%H:%M')}, "
                       f"dusk {daylight.civil_twilight_end.strftime('%H:%M')}")
        except Exception as e:
            logger.error(f"Failed to fetch daylight info: {e}")
            # Continue evaluation without daylight data

    # Run threshold checks
    all_violations = []

    # Weather checks
    if weather:
        weather_violations = check_weather_thresholds(weather, config)
        all_violations.extend(weather_violations)

    # Trail checks (check each activity type)
    if trail and practice.activities:
        for activity in practice.activities:
            trail_violations = check_trail_thresholds(trail, activity.name, config)
            all_violations.extend(trail_violations)

    # Lead availability check (skip for 7am weather-only check)
    lead_violations = check_lead_availability(practice, config, skip_lead_check=skip_lead_check)
    all_violations.extend(lead_violations)

    # Daylight checks
    if daylight:
        daylight_violations = check_daylight(practice, daylight, config)
        all_violations.extend(daylight_violations)

    # Event conflict checks
    try:
        location_name = practice.location.name if practice.location else None
        conflicts = get_event_conflicts(practice.date, location_name)
        evaluation.event_conflicts = conflicts

        if conflicts:
            logger.info(f"Found {len(conflicts)} event conflicts")
            conflict_violations = check_event_conflicts(conflicts, config)
            all_violations.extend(conflict_violations)
    except Exception as e:
        logger.error(f"Failed to check event conflicts: {e}")
        # Continue evaluation without event conflict data

    # Air quality checks
    if practice.location and practice.location.latitude and practice.location.longitude:
        try:
            aqi_info = get_air_quality(
                lat=practice.location.latitude,
                lon=practice.location.longitude
            )
            if aqi_info:
                evaluation.air_quality = {
                    'aqi': aqi_info.aqi,
                    'category': aqi_info.category,
                    'pollutant': aqi_info.pollutant
                }
                logger.info(f"AQI: {aqi_info.aqi} ({aqi_info.category})")
                aqi_violations = check_air_quality(aqi_info.aqi, aqi_info.category, config)
                all_violations.extend(aqi_violations)
        except Exception as e:
            logger.error(f"Failed to check air quality: {e}")
            # Continue evaluation without AQI data

    # Update evaluation with violations
    evaluation.violations = all_violations

    # Check lead/workout status
    evaluation.has_confirmed_lead = any(lead.confirmed for lead in practice.leads)
    evaluation.has_posted_workout = bool(practice.workout_description)

    # Determine overall go/no-go
    # Critical violations mean no-go
    critical_violations = [v for v in all_violations if v.severity == 'critical']

    if critical_violations:
        evaluation.is_go = False
        logger.warning(f"Practice {practice.id}: NO-GO - {len(critical_violations)} critical violations")
    else:
        evaluation.is_go = True
        if all_violations:
            logger.info(f"Practice {practice.id}: GO with {len(all_violations)} warnings")
        else:
            logger.info(f"Practice {practice.id}: GO - all clear")

    # Set confidence based on data availability
    data_sources = sum([
        weather is not None,
        trail is not None,
        daylight is not None
    ])
    evaluation.confidence = data_sources / 3.0  # 0.33, 0.66, or 1.0

    return evaluation


def should_propose_cancellation(evaluation: PracticeEvaluation) -> bool:
    """
    Determine if an evaluation warrants a cancellation proposal.

    Args:
        evaluation: Practice evaluation result

    Returns:
        True if cancellation should be proposed to humans
    """
    # If practice can't proceed (is_go = False), propose cancellation
    if not evaluation.is_go:
        logger.info(f"Proposing cancellation for practice {evaluation.practice_id}")
        return True

    # If there are multiple warnings, may want to flag for review
    # For now, only propose on critical violations (is_go = False)
    warning_violations = [v for v in evaluation.violations if v.severity == 'warning']
    if len(warning_violations) >= 3:
        logger.info(f"Flagging practice {evaluation.practice_id} for review: {len(warning_violations)} warnings")
        # Could add a "review" status here, but for now only critical = cancellation proposal

    return False
