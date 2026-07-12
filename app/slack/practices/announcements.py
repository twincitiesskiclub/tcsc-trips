"""Practice posting and update operations."""

from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db
from app.slack.client import get_slack_client, get_channel_id_by_name
from app.slack.blocks import (
    build_practice_announcement_blocks,
    build_combined_lift_blocks,
    build_practice_details_blocks,
)
from app.practices.models import Practice
from app.practices.interfaces import (
    AnnouncementConditions,
    TrailCondition,
    WeatherConditions,
)

from app.slack.practices._config import (
    _get_announcement_channel,
    get_default_duration_minutes,
)


_UNSET = object()


def _gather_conditions(practice, *, weather=_UNSET, trail_conditions=_UNSET):
    """Fetch each external condition at most once for one render."""
    has_coordinates = bool(
        practice.location
        and practice.location.latitude is not None
        and practice.location.longitude is not None
    )
    resolved_weather = None if weather is _UNSET else weather
    resolved_trails = None if trail_conditions is _UNSET else trail_conditions
    daylight = None
    aqi = None
    if has_coordinates:
        lat = practice.location.latitude
        lon = practice.location.longitude
        if weather is _UNSET:
            try:
                from app.integrations.weather import get_weather_for_location
                resolved_weather = get_weather_for_location(lat, lon, practice.date)
            except Exception as exc:
                current_app.logger.warning(
                    "weather fetch failed for practice #%s: %s", practice.id, exc
                )
        try:
            from app.integrations.daylight import get_daylight_info
            daylight = get_daylight_info(lat, lon, practice.date)
        except Exception as exc:
            current_app.logger.warning(
                "daylight fetch failed for practice #%s: %s", practice.id, exc
            )
        try:
            from app.integrations.air_quality import get_air_quality
            air_info = get_air_quality(lat, lon)
            aqi = air_info.aqi if air_info else None
        except Exception as exc:
            current_app.logger.warning(
                "AQI fetch failed for practice #%s: %s", practice.id, exc
            )
    return AnnouncementConditions(
        weather=resolved_weather,
        daylight=daylight,
        air_quality=aqi,
        trail_conditions=resolved_trails,
        duration_minutes=get_default_duration_minutes(),
    )


def _upsert_combined_details_reply(client, practices: list) -> None:
    """Post or update the threaded 'Practice Details' reply for a combined-lift post.

    Combined-lift posts are indoor strength sessions (no weather/daylight/AQI).
    The reply contains only the header + Parking/Gear sections from the first
    (location-bearing) practice in the group.

    Saves/updates slack_details_ts on ALL practices in the group so the ts stays
    consistent regardless of which practice triggers the refresh.

    Best-effort: any exception is caught and logged.
    """
    if not practices:
        return
    try:
        from app.practices.service import convert_practice_to_info
        # Use first practice as the representative (has location/gear data)
        rep = practices[0]
        practice_info = convert_practice_to_info(rep)
        # No weather/daylight/AQI for indoor strength sessions
        blocks = build_practice_details_blocks(practice_info)
        if not blocks:
            return

        # All practices in the group share the same slack_message_ts / channel_id
        channel_id = rep.slack_channel_id
        thread_ts = rep.slack_message_ts

        # Determine existing details_ts (any non-None value across the group is canonical)
        existing_ts = next((p.slack_details_ts for p in practices if p.slack_details_ts), None)

        if existing_ts:
            client.chat_update(
                channel=channel_id,
                ts=existing_ts,
                blocks=blocks,
                text="Practice details",
            )
        else:
            reply = client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                blocks=blocks,
                text="Practice details",
                reply_broadcast=False,
                unfurl_links=False,
                unfurl_media=False,
            )
            ts = reply.get("ts")
            if ts:
                for p in practices:
                    p.slack_details_ts = ts
                db.session.commit()
    except Exception as e:
        current_app.logger.warning(
            f"Could not upsert combined details reply for practices "
            f"{[p.id for p in practices]}: {e}"
        )


def _upsert_details_reply(
    client,
    practice,
    practice_info,
    weather=_UNSET,
    trail_conditions=_UNSET,
):
    """Post or update the threaded 'Practice Details' reply. Best-effort.

    Creates a new thread reply when slack_details_ts is absent (initial post or
    backfill after an edit). Updates the existing reply otherwise.
    Saves slack_details_ts to the practice row on first creation.
    """
    try:
        conditions = _gather_conditions(
            practice,
            weather=weather,
            trail_conditions=trail_conditions,
        )
        blocks = build_practice_details_blocks(
            practice_info,
            weather=conditions.weather,
            trail_conditions=conditions.trail_conditions,
            daylight=conditions.daylight,
            air_quality=conditions.air_quality,
        )
        if not blocks:
            return
        if practice.slack_details_ts:
            client.chat_update(
                channel=practice.slack_channel_id,
                ts=practice.slack_details_ts,
                blocks=blocks,
                text="Practice details",
            )
        else:
            reply = client.chat_postMessage(
                channel=practice.slack_channel_id,
                thread_ts=practice.slack_message_ts,
                blocks=blocks,
                text="Practice details",
                reply_broadcast=False,
                unfurl_links=False,
                unfurl_media=False,
            )
            # Only persist a real ts; saving None would make the next refresh
            # post a second reply. Known/accepted gap: if the process dies
            # between this post succeeding and the commit below, no ts is
            # persisted, so a later refresh will post a duplicate reply.
            ts = reply.get('ts')
            if ts:
                practice.slack_details_ts = ts
                db.session.commit()
    except Exception as e:
        current_app.logger.warning(
            f"Could not upsert practice details reply for #{practice.id}: {e}"
        )


def post_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = _UNSET,
    trail_conditions: Optional[TrailCondition] = _UNSET,
    channel_override: Optional[str] = None
) -> dict:
    """Post practice announcement to #practices channel.

    Also immediately posts the going list thread reply so there's always
    a linkable thread for RSVPs.

    Args:
        practice: Practice SQLAlchemy model
        weather: Weather conditions (optional)
        trail_conditions: Trail conditions (optional)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    rendered_weather = None if weather is _UNSET else weather
    rendered_trails = None if trail_conditions is _UNSET else trail_conditions
    blocks = build_practice_announcement_blocks(
        practice_info,
        rendered_weather,
        rendered_trails,
    )

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}",  # Fallback text
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted practice announcement for practice #{practice.id} (ts: {message_ts})")

        # Save slack info to practice
        practice.slack_message_ts = message_ts
        practice.slack_channel_id = channel_id
        db.session.commit()

        # Post the threaded "Practice Details" reply (sunset/wind/AQI/parking/gear)
        _upsert_details_reply(client, practice, practice_info, weather=weather, trail_conditions=trail_conditions)

        # Add pre-seeded checkmark emoji for RSVP
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name="white_check_mark"
            )
            # Add evergreen tree for interval practices (endurance option)
            has_intervals = any(getattr(t, 'has_intervals', False) for t in practice.practice_types) if practice.practice_types else False
            if has_intervals:
                client.reactions_add(
                    channel=channel_id,
                    timestamp=message_ts,
                    name="evergreen_tree"
                )
        except Exception as e:
            current_app.logger.warning(f"Could not add reaction: {e}")

        # Create logging thread in #tcsc-logging
        try:
            from app.slack.practices.coach_review import create_practice_log_thread
            create_practice_log_thread(practice)
        except Exception as e:
            current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_combined_lift_announcement(
    practices: list[Practice],
    channel_override: Optional[str] = None
) -> dict:
    """Post combined lift announcement for multiple lift practices.

    Used when 2-3 lift practices (e.g., Wed + Fri at Balance Fitness) should
    be announced together in a single message with per-day RSVP emojis.

    Args:
        practices: List of Practice SQLAlchemy models (2-3 practices)
        channel_override: Optional channel name to override default

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    if not practices:
        return {'success': False, 'error': 'No practices provided'}

    client = get_slack_client()

    # Determine channel
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy models to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Sort practices by date for consistent emoji assignment
    sorted_practices = sorted(practices, key=lambda p: p.date)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in sorted_practices]
    days_str = " & ".join(days)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        practice_ids = [p.id for p in sorted_practices]
        current_app.logger.info(f"Posted combined lift announcement for practices {practice_ids} (ts: {message_ts})")

        # Save slack info to all practices
        for practice in sorted_practices:
            practice.slack_message_ts = message_ts
            practice.slack_channel_id = channel_id
        db.session.commit()

        # Add RSVP emojis for each session — hour-based when possible
        # (e.g. :six: for 6:10 PM, :seven: for 7:20 PM), matching the
        # block builder's per-slot emoji.
        from app.slack.client import get_combined_practice_emojis
        rsvp_emojis = get_combined_practice_emojis(sorted_practices)
        for i, practice in enumerate(sorted_practices):
            emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else "white_check_mark"
            try:
                client.reactions_add(
                    channel=channel_id,
                    timestamp=message_ts,
                    name=emoji
                )
            except Exception as e:
                current_app.logger.warning(f"Could not add {emoji} reaction: {e}")

        # Post threaded "Practice Details" reply (parking + gear; no weather for indoor)
        _upsert_combined_details_reply(client, sorted_practices)

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting combined lift announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = _UNSET,
    trail_conditions: Optional[TrailCondition] = _UNSET,
) -> dict:
    """Update an existing practice announcement message.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        weather: Updated weather conditions (optional)
        trail_conditions: Updated trail conditions (optional)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks
    rendered_weather = None if weather is _UNSET else weather
    rendered_trails = None if trail_conditions is _UNSET else trail_conditions
    blocks = build_practice_announcement_blocks(
        practice_info,
        rendered_weather,
        rendered_trails,
    )

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        # Update (or backfill) the threaded "Practice Details" reply
        _upsert_details_reply(client, practice, practice_info, weather=weather, trail_conditions=trail_conditions)

        current_app.logger.info(f"Updated practice announcement for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_post(practice: Practice) -> dict:
    """Update the main practice announcement post with current data.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No practice message to update'}

    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks (without weather/trail data)
    blocks = build_practice_announcement_blocks(practice_info)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        # Update (or backfill) the threaded "Practice Details" reply (no weather on edit path)
        _upsert_details_reply(client, practice, practice_info)

        current_app.logger.info(f"Updated practice post for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice post: {error_msg}")
        return {'success': False, 'error': error_msg}


def is_combined_lift_practice(practice: Practice) -> bool:
    """Check if practice is part of a combined lift post.

    A practice is part of a combined lift if:
    1. It has slack_message_ts set
    2. Another practice shares the same slack_message_ts

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        True if practice is part of a combined post with other practices.
    """
    if not practice.slack_message_ts:
        return False

    # Count how many practices share this message_ts
    count = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).count()

    return count > 1


def update_combined_lift_post(practice: Practice) -> dict:
    """Update combined lift announcement when any practice in it changes.

    Finds all practices sharing the same slack_message_ts and rebuilds
    the combined block structure.

    Args:
        practice: Practice SQLAlchemy model (one of the combined practices)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Find all practices sharing this message_ts
    practices = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).order_by(Practice.date).all()

    if not practices:
        return {'success': False, 'error': 'No practices found for this message'}

    # Convert to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in practices]
    days_str = " & ".join(days)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}"
        )

        # Update (or backfill) the threaded "Practice Details" reply
        _upsert_combined_details_reply(client, practices)

        practice_ids = [p.id for p in practices]
        current_app.logger.info(f"Updated combined lift post for practices {practice_ids}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating combined lift post: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_slack_post(practice: Practice) -> dict:
    """Smart update that handles both individual and combined posts.

    Detects whether the practice is part of a combined lift post and
    uses the appropriate update function.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts:
        return {'success': False, 'error': 'No Slack post to update'}

    if is_combined_lift_practice(practice):
        return update_combined_lift_post(practice)
    else:
        return update_practice_post(practice)
