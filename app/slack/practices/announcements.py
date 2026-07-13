"""Practice posting and update operations."""

from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db
from app.slack.client import (
    assign_combined_session_emojis,
    get_channel_id_by_name,
    get_slack_client,
)
from app.slack.blocks import (
    build_combined_fallback_text,
    build_practice_announcement_blocks,
    build_combined_lift_blocks,
    build_practice_details_blocks,
    build_practice_details_fallback_text,
    build_practice_fallback_text,
    guard_fallback_text,
    guard_slack_blocks,
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


def convert_practice_to_info(practice):
    """Late-bound model conversion keeps the Slack layer easy to isolate."""
    from app.practices.service import convert_practice_to_info as convert

    return convert(practice)


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


def _combined_details_payload(practices):
    """Render shared Details once, or label divergent per-session content."""
    conditions = AnnouncementConditions()
    rendered = []
    for practice in practices:
        info = convert_practice_to_info(practice)
        child_blocks = build_practice_details_blocks(info, conditions)
        if not child_blocks:
            continue
        content_blocks = [
            block for block in child_blocks if block.get("type") != "header"
        ]
        rendered.append((
            practice,
            content_blocks,
            build_practice_details_fallback_text(info, conditions),
        ))
    if not rendered:
        return [], ""

    common = (
        len(rendered) == len(practices)
        and all(item[1] == rendered[0][1] for item in rendered[1:])
    )
    if common:
        practice, content, fallback = rendered[0]
        blocks = [{
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Practice Details",
                "emoji": True,
            },
        }] + content
        return (
            guard_slack_blocks(
                blocks,
                surface="combined_practice_details",
                practice_id=practice.id,
            ),
            fallback,
        )

    groups = []
    fallback_parts = ["Combined practice details."]
    for practice, content, fallback in rendered:
        groups.append([{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*:{practice.slack_session_emoji}: "
                    f"{practice.date.strftime('%A at %-I:%M %p')}*"
                ),
            },
        }] + content)
        fallback_parts.append(f":{practice.slack_session_emoji}: {fallback}")
    blocks = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Practice Details",
            "emoji": True,
        },
    }]
    for group in groups:
        if len(blocks) > 1:
            blocks.append({"type": "divider"})
        blocks.extend(group)
    return (
        guard_slack_blocks(
            blocks,
            surface="combined_practice_details",
            practice_id=practices[0].id,
        ),
        guard_fallback_text(
            " ".join(fallback_parts),
            surface="combined_practice_details",
            practice_id=practices[0].id,
        ),
    )


def _upsert_combined_details_reply(client, practices):
    """Create, update, or delete the canonical combined Details reply."""
    if not practices:
        return {"success": True, "skipped": "no_practices"}
    representative = practices[0]
    original = {
        practice.id: practice.slack_details_ts for practice in practices
    }
    existing = next((value for value in original.values() if value), None)
    try:
        blocks, fallback = _combined_details_payload(practices)
        if not blocks:
            if not existing:
                return {"success": True, "skipped": "no_details"}
            client.chat_delete(
                channel=representative.slack_channel_id,
                ts=existing,
            )
            for practice in practices:
                practice.slack_details_ts = None
            db.session.commit()
            return {"success": True, "deleted": True}

        if existing:
            client.chat_update(
                channel=representative.slack_channel_id,
                ts=existing,
                blocks=blocks,
                text=fallback,
            )
            for practice in practices:
                practice.slack_details_ts = existing
            db.session.commit()
            return {"success": True, "updated": True}

        response = client.chat_postMessage(
            channel=representative.slack_channel_id,
            thread_ts=representative.slack_message_ts,
            blocks=blocks,
            text=fallback,
            reply_broadcast=False,
            unfurl_links=False,
            unfurl_media=False,
        )
        details_ts = response.get("ts")
        if not details_ts:
            return {
                "success": False,
                "error": "Slack returned no Details timestamp",
            }
        for practice in practices:
            practice.slack_details_ts = details_ts
        db.session.commit()
        return {"success": True, "message_ts": details_ts}
    except Exception as exc:
        for practice in practices:
            practice.slack_details_ts = original[practice.id]
        try:
            db.session.rollback()
        except Exception:
            current_app.logger.warning(
                "Could not roll back combined Details sync",
                exc_info=True,
            )
        current_app.logger.warning(
            "Could not sync combined Details reply for practices %s: %s",
            [practice.id for practice in practices],
            exc,
        )
        return {"success": False, "error": str(exc)}


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

    clear_stale_session = not practice.slack_message_ts
    if clear_stale_session:
        practice.slack_session_emoji = None

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
        db.session.rollback()
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def _combined_infos(practices):
    return [convert_practice_to_info(item) for item in practices]


def _shared_plan_names(practices):
    from app.slack.blocks.announcements import _shared_plan_reactions

    return plan_reaction_names(_shared_plan_reactions(_combined_infos(practices)))


def _seed_combined_reactions(client, practices):
    names = [item.slack_session_emoji for item in practices]
    names.extend(_shared_plan_names(practices))
    for name in dict.fromkeys(names):
        try:
            client.reactions_add(
                channel=practices[0].slack_channel_id,
                timestamp=practices[0].slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not seed :%s: on combined root %s: %s",
                    name,
                    practices[0].slack_message_ts,
                    exc,
                )


def _remove_combined_seed(client, practices, name):
    try:
        client.reactions_remove(
            channel=practices[0].slack_channel_id,
            timestamp=practices[0].slack_message_ts,
            name=name,
        )
    except Exception as exc:
        if _reaction_error_name(exc) != "no_reaction":
            current_app.logger.warning(
                "Could not remove :%s: from combined root %s: %s",
                name,
                practices[0].slack_message_ts,
                exc,
            )


def _reconcile_combined_plan_reactions(
    client,
    practices,
    *,
    previous_plan_reactions=None,
):
    desired = set(_shared_plan_names(practices))
    known = set(plan_reaction_names(previous_plan_reactions or []))
    for practice in practices:
        known.update(plan_reaction_names(practice.plan_reactions or []))
    for name in sorted(known - desired):
        _remove_combined_seed(client, practices, name)
    for name in sorted(desired):
        try:
            client.reactions_add(
                channel=practices[0].slack_channel_id,
                timestamp=practices[0].slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not add :%s: to combined root %s: %s",
                    name,
                    practices[0].slack_message_ts,
                    exc,
                )


def post_combined_lift_announcement(practices, channel_override=None):
    """Post one combined root after persisting its attendance mapping."""
    if not 2 <= len(practices) <= 3:
        return {
            "success": False,
            "error": "Combined posts require 2 or 3 practices",
        }
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    assignment = assign_combined_session_emojis(ordered)
    if not assignment["success"]:
        return {**assignment, "safe_to_fallback": True}

    channel_id = (
        get_channel_id_by_name(channel_override.lstrip("#"))
        if channel_override else _get_announcement_channel()
    )
    if not channel_id:
        return {"success": False, "error": "Could not find announcement channel"}
    infos = _combined_infos(ordered)
    blocks = build_combined_lift_blocks(infos)
    fallback = build_combined_fallback_text(infos)
    client = get_slack_client()
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback,
            unfurl_links=False,
            unfurl_media=False,
        )
        message_ts = response.get("ts")
        if not message_ts:
            return {
                "success": False,
                "error": "Slack did not return a message timestamp",
            }
        for practice in ordered:
            practice.slack_channel_id = channel_id
            practice.slack_message_ts = message_ts
        db.session.commit()
        details = _upsert_combined_details_reply(client, ordered)
        _seed_combined_reactions(client, ordered)
        current_app.logger.info(
            "Posted combined Strength announcement for practices %s (ts: %s)",
            [item.id for item in ordered],
            message_ts,
        )
        return {
            "success": True,
            "message_ts": message_ts,
            "channel_id": channel_id,
            "details": details,
        }
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error(
            "Error posting combined Strength announcement: %s", error
        )
        return {"success": False, "error": error}


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


def get_announcement_siblings(practice, *, exclude_practice_id=None):
    """Return only rows sharing this exact Slack channel and root timestamp."""
    query = Practice.query.filter_by(
        slack_channel_id=practice.slack_channel_id,
        slack_message_ts=practice.slack_message_ts,
    )
    if exclude_practice_id is not None:
        query = query.filter(Practice.id != exclude_practice_id)
    return query.order_by(Practice.date, Practice.id).all()


def is_combined_lift_practice(practice: Practice) -> bool:
    """Recognize persisted and legacy combined roots, including one survivor."""
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return False
    if (practice.slack_session_emoji or "").strip():
        return True
    return len(get_announcement_siblings(practice)) > 1


def update_combined_lift_post(
    practice,
    *,
    exclude_practice_id=None,
    previous_plan_reactions=None,
    announcement_notice=None,
):
    """Rebuild an existing combined root without remapping saved reactions."""
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {"success": False, "error": "No Slack message to update"}
    all_siblings = get_announcement_siblings(practice)
    if not all_siblings:
        return {"success": False, "error": "No practices found for this message"}
    assignment = assign_combined_session_emojis(all_siblings)
    if not assignment["success"]:
        return assignment
    removed = next(
        (item for item in all_siblings if item.id == exclude_practice_id),
        None,
    )
    siblings = [
        item for item in all_siblings if item.id != exclude_practice_id
    ]
    if not siblings:
        return {"success": False, "error": "No surviving practices for this message"}

    infos = _combined_infos(siblings)
    blocks = build_combined_lift_blocks(
        infos, announcement_notice=announcement_notice
    )
    fallback = build_combined_fallback_text(
        infos, announcement_notice=announcement_notice
    )
    client = get_slack_client()
    details = None
    if exclude_practice_id is not None:
        details = _upsert_combined_details_reply(client, siblings)
        if not details.get("success"):
            return {
                "success": False,
                "error": "Combined Details did not sync; root was not changed",
                "details": details,
            }
    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
        )
        if details is None:
            details = _upsert_combined_details_reply(client, siblings)
        _reconcile_combined_plan_reactions(
            client,
            siblings,
            previous_plan_reactions=previous_plan_reactions,
        )
        if removed and removed.slack_session_emoji:
            _remove_combined_seed(
                client, siblings, removed.slack_session_emoji
            )
        current_app.logger.info(
            "Updated combined Strength root for practices %s",
            [item.id for item in siblings],
        )
        return {"success": True, "details": details}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error(
            "Error updating combined Strength announcement: %s", error
        )
        return {"success": False, "error": error}


def _delete_slack_message(client, *, channel, ts):
    """Delete one Slack message, treating an already-absent row as success."""
    try:
        client.chat_delete(channel=channel, ts=ts)
        return {"success": True}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        if error == "message_not_found":
            return {"success": True, "skipped": "already_absent"}
        return {"success": False, "error": error}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def remove_practice_from_announcement(practice):
    """Remove one practice while preserving any shared announcement root."""
    if not practice.slack_message_ts:
        return {"success": True, "skipped": "absent"}
    if not practice.slack_channel_id:
        return {"success": False, "error": "Slack message has no channel"}

    survivors = get_announcement_siblings(
        practice,
        exclude_practice_id=practice.id,
    )
    if survivors:
        try:
            return update_combined_lift_post(
                practice,
                exclude_practice_id=practice.id,
                previous_plan_reactions=practice.plan_reactions or [],
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    client = get_slack_client()
    if practice.slack_details_ts:
        details_result = _delete_slack_message(
            client,
            channel=practice.slack_channel_id,
            ts=practice.slack_details_ts,
        )
        if not details_result["success"]:
            return details_result
        practice.slack_details_ts = None
        db.session.commit()

    root_result = _delete_slack_message(
        client,
        channel=practice.slack_channel_id,
        ts=practice.slack_message_ts,
    )
    if not root_result["success"]:
        return root_result
    practice.slack_message_ts = None
    practice.slack_channel_id = None
    db.session.commit()
    return {"success": True}


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
        return update_combined_lift_post(
            practice,
            announcement_notice=announcement_notice,
            previous_plan_reactions=previous_plan_reactions,
        )
    return update_practice_post(
        practice,
        announcement_notice=announcement_notice,
        previous_plan_reactions=previous_plan_reactions,
    )
