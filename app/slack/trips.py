"""Slack side-effects for trip registrations. Every function returns bool
and never raises - trip flows must not fail because Slack did."""
import os

from flask import current_app

from app.slack.client import (
    add_user_to_channel, get_channel_id_by_name, get_slack_client,
)
from app.slack.blocks.trips import (
    build_confirmation_dm_blocks, build_registration_dm_blocks,
    confirmation_dm_fallback, registration_dm_fallback,
)


def base_url():
    return os.environ.get('EXTERNAL_BASE_URL', 'https://tcsc.ski')


def _slack_uid(registration):
    user = registration.user
    if user and user.slack_user and user.slack_user.slack_uid:
        return user.slack_user.slack_uid
    return None


def _send_dm(registration, blocks, fallback):
    slack_uid = _slack_uid(registration)
    if not slack_uid:
        current_app.logger.info(
            "trip slack: no linked SlackUser for registration %s",
            registration.id)
        return False
    try:
        get_slack_client().chat_postMessage(
            channel=slack_uid, blocks=blocks, text=fallback)
        return True
    except Exception as exc:
        current_app.logger.warning(
            "trip slack: DM failed for registration %s: %s",
            registration.id, exc)
        return False


def send_registration_dm(registration):
    trip = registration.trip
    return _send_dm(
        registration,
        build_registration_dm_blocks(registration, trip, trip.series),
        registration_dm_fallback(registration, trip))


def send_confirmation_dm(registration):
    trip = registration.trip
    return _send_dm(
        registration,
        build_confirmation_dm_blocks(registration, trip, trip.series),
        confirmation_dm_fallback(registration, trip))


def invite_to_trip_channel(registration):
    trip = registration.trip
    channel_name = trip.series.slack_channel_name if trip.series else None
    if not channel_name:
        return False
    slack_uid = _slack_uid(registration)
    if not slack_uid:
        return False
    try:
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            current_app.logger.warning(
                "trip slack: channel %s not found", channel_name)
            return False
        return add_user_to_channel(slack_uid, channel_id,
                                   registration.user.email)
    except Exception as exc:
        current_app.logger.warning(
            "trip slack: invite failed for registration %s: %s",
            registration.id, exc)
        return False
