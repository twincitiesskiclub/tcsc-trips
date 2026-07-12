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
    build_practice_details_fallback_text,
    build_practice_fallback_text,
)
from app.practices.plan_reactions import plan_reaction_names
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
    if (
        trail_conditions is _UNSET
        and practice.location
        and practice.location.name
    ):
        try:
            from app.integrations.trail_conditions import get_trail_conditions
            resolved_trails = get_trail_conditions(practice.location.name)
        except Exception as exc:
            current_app.logger.warning(
                "trail conditions fetch failed for practice #%s: %s",
                practice.id,
                exc,
            )
    return AnnouncementConditions(
        weather=resolved_weather,
        daylight=daylight,
        air_quality=aqi,
        trail_conditions=resolved_trails,
        duration_minutes=get_default_duration_minutes(),
    )


def _conditions_for_render(
    practice, *, weather=_UNSET, trail_conditions=_UNSET
):
    """Resolve one render snapshot while preserving explicit unavailable values."""
    overrides = {}
    if weather is not _UNSET:
        overrides["weather"] = weather
    if trail_conditions is not _UNSET:
        overrides["trail_conditions"] = trail_conditions
    return _gather_conditions(practice, **overrides)


def build_announcement_change_notice(
    *, previous_date, previous_location_id, practice
):
    """Describe a date/time or location change for one Slack refresh only."""
    time_changed = previous_date != practice.date
    location_changed = previous_location_id != practice.location_id
    if time_changed and location_changed:
        return (
            "🕒 Date/time and location updated, check the heading and Where below."
        )
    if time_changed:
        return "🕒 Date or time updated, check the heading above."
    if location_changed:
        return "📍 Location updated, check Where below."
    return None


def _reaction_error_name(exc):
    response = getattr(exc, "response", None)
    return response.get("error") if response else None


def _seed_plan_reactions(client, practice):
    try:
        names = ["white_check_mark"] + plan_reaction_names(
            practice.plan_reactions or []
        )
    except Exception as exc:
        current_app.logger.warning(
            "Could not read Plan reactions for practice #%s: %s",
            practice.id,
            exc,
        )
        names = ["white_check_mark"]
    for name in names:
        try:
            client.reactions_add(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not seed :%s: on practice #%s: %s",
                    name,
                    practice.id,
                    exc,
                )


def _reconcile_plan_reactions(
    client,
    practice,
    *,
    previous_plan_reactions=None,
):
    try:
        previous = set(plan_reaction_names(previous_plan_reactions or []))
        current = set(plan_reaction_names(practice.plan_reactions or []))
    except Exception as exc:
        current_app.logger.warning(
            "Could not read Plan reactions for practice #%s: %s",
            practice.id,
            exc,
        )
        return
    for name in sorted(previous - current):
        try:
            client.reactions_remove(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "no_reaction":
                current_app.logger.warning(
                    "Could not remove :%s: from practice #%s: %s",
                    name,
                    practice.id,
                    exc,
                )
    for name in sorted(current - previous):
        try:
            client.reactions_add(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not add :%s: to practice #%s: %s",
                    name,
                    practice.id,
                    exc,
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
    conditions,
):
    """Post or update the threaded 'Practice Details' reply. Best-effort.

    Creates a reply when absent, updates it while content remains, and deletes
    a stale reply when rebuilt Details are empty. Timestamp changes are saved
    only after the corresponding Slack write succeeds.
    """
    original_ts = practice.slack_details_ts
    try:
        blocks = build_practice_details_blocks(practice_info, conditions)
        if not blocks:
            if not original_ts:
                return {"success": True, "skipped": "no_details"}
            client.chat_delete(
                channel=practice.slack_channel_id,
                ts=original_ts,
            )
            practice.slack_details_ts = None
            db.session.commit()
            return {"success": True, "deleted": True}

        fallback = build_practice_details_fallback_text(
            practice_info, conditions
        )
        if original_ts:
            client.chat_update(
                channel=practice.slack_channel_id,
                ts=original_ts,
                blocks=blocks,
                text=fallback,
            )
            return {"success": True, "updated": True}

        reply = client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
            reply_broadcast=False,
            unfurl_links=False,
            unfurl_media=False,
        )
        details_ts = reply.get("ts")
        if not details_ts:
            return {
                "success": False,
                "error": "Slack did not return a Details timestamp",
            }
        practice.slack_details_ts = details_ts
        db.session.commit()
        return {"success": True, "message_ts": details_ts}
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            current_app.logger.warning(
                "Could not roll back practice Details sync for #%s: %s",
                practice.id,
                rollback_exc,
            )
        practice.slack_details_ts = original_ts
        current_app.logger.warning(
            "Could not sync practice Details reply for #%s: %s",
            practice.id,
            exc,
        )
        return {"success": False, "error": str(exc)}


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

    conditions = _conditions_for_render(
        practice,
        weather=weather,
        trail_conditions=trail_conditions,
    )

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    blocks = build_practice_announcement_blocks(practice_info, conditions)
    fallback = build_practice_fallback_text(practice_info, conditions)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback,
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
        _upsert_details_reply(client, practice, practice_info, conditions)
        _seed_plan_reactions(client, practice)

        # Create logging thread in #tcsc-logging
        try:
            from app.slack.practices.coach_review import create_practice_log_thread
            create_practice_log_thread(practice)
        except Exception as e:
            current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id,
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
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
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
    conditions = _conditions_for_render(
        practice,
        weather=weather,
        trail_conditions=trail_conditions,
    )

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    blocks = build_practice_announcement_blocks(
        practice_info,
        conditions,
        announcement_notice=announcement_notice,
    )
    fallback = build_practice_fallback_text(
        practice_info,
        conditions,
        announcement_notice=announcement_notice,
    )

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
        )

        _reconcile_plan_reactions(
            client,
            practice,
            previous_plan_reactions=previous_plan_reactions,
        )
        details_result = _upsert_details_reply(
            client, practice, practice_info, conditions
        )

        current_app.logger.info(f"Updated practice announcement for practice #{practice.id}")
        return {'success': True, 'details': details_result}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_post(
    practice: Practice,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
) -> dict:
    """Update the main practice announcement post with current data.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    return update_practice_announcement(
        practice,
        announcement_notice=announcement_notice,
        previous_plan_reactions=previous_plan_reactions,
    )


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


def update_practice_slack_post(
    practice: Practice,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
) -> dict:
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
        return update_practice_post(
            practice,
            announcement_notice=announcement_notice,
            previous_plan_reactions=previous_plan_reactions,
        )
