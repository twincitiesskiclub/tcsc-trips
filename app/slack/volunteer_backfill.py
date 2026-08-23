"""Slack backfill for the volunteer-interest question.

Members who registered before the Get Involved question shipped have
``UserSeason.volunteer_interests`` NULL. An admin triggers this from the
seasons page; each eligible member gets one DM carrying the whole form
(see ``app.slack.blocks.volunteer``). Re-triggering skips anyone who has
answered or was asked within the cooldown, so the same button doubles as
the reminder mechanism.

Like the availability nudge, a failed DM to one member must never abort
the run for the rest, and only a successful send stamps
``volunteer_asked_at`` (a failed send stays eligible for the next run).
"""

from datetime import datetime, timedelta

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.constants import UserSeasonStatus
from app.models import db, SlackUser, User, UserSeason
from app.slack.blocks.volunteer import build_volunteer_ask_blocks
from app.slack.client import get_slack_client
from app.utils import validate_volunteer_selections

ASK_COOLDOWN = timedelta(days=3)

# Only members still in the season get asked; dropped members must not be
# DMed about volunteering for a season they are no longer part of.
_ASKABLE_STATUSES = (UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY)


def _unanswered(season_id):
    """(User, UserSeason) rows still in the season with no volunteer answer."""
    return (
        db.session.query(User, UserSeason)
        .join(UserSeason, User.id == UserSeason.user_id)
        .filter(UserSeason.season_id == season_id,
                UserSeason.status.in_(_ASKABLE_STATUSES),
                UserSeason.volunteer_interests.is_(None))
        .all()
    )


def eligible_members(season_id) -> list[tuple]:
    """(User, SlackUser) pairs to DM now: no answer, linked Slack account,
    and not asked within the cooldown.
    """
    cutoff = datetime.utcnow() - ASK_COOLDOWN
    out = []
    for user, us in _unanswered(season_id):
        if not user.slack_user_id:
            continue
        if us.volunteer_asked_at and us.volunteer_asked_at > cutoff:
            continue
        slack_user = db.session.get(SlackUser, user.slack_user_id)
        if slack_user is None:
            continue
        out.append((user, slack_user))
    return out


def backfill_stats(season_id) -> dict:
    """Counts for the admin confirm dialog."""
    cutoff = datetime.utcnow() - ASK_COOLDOWN
    eligible = no_slack = cooldown = 0
    for user, us in _unanswered(season_id):
        if not user.slack_user_id:
            no_slack += 1
        elif us.volunteer_asked_at and us.volunteer_asked_at > cutoff:
            cooldown += 1
        else:
            eligible += 1
    return {"eligible": eligible, "no_slack": no_slack, "cooldown": cooldown}


def send_backfill_asks(season_id) -> dict:
    """DM every eligible member. Returns {'sent': n, 'failed': m}."""
    sent = failed = 0
    for user, slack_user in eligible_members(season_id):
        blocks = build_volunteer_ask_blocks(user.first_name, season_id)
        fallback = ("One thing we missed when you registered: how you'd "
                    "like to pitch in this season.")
        try:
            get_slack_client().chat_postMessage(
                channel=slack_user.slack_uid, blocks=blocks, text=fallback)
        except SlackApiError as exc:
            current_app.logger.warning(
                "Volunteer ask DM to %s failed: %s",
                slack_user.slack_uid, exc.response.get("error", exc))
            failed += 1
            continue
        except Exception as exc:  # noqa: BLE001 - no token / transport errors
            current_app.logger.warning(
                "Volunteer ask DM to %s failed: %s", slack_user.slack_uid, exc)
            failed += 1
            continue
        us = UserSeason.get_for_user_season(user.id, season_id)
        us.volunteer_asked_at = datetime.utcnow()
        sent += 1
    db.session.commit()
    return {"sent": sent, "failed": failed}


def _selected(state_values: dict, block_id: str, action_id: str) -> list[str]:
    block = (state_values or {}).get(block_id) or {}
    element = block.get(action_id) or {}
    return [o.get("value") for o in element.get("selected_options") or []]


def process_volunteer_submit(slack_uid: str, season_id: int,
                             state_values: dict) -> dict:
    """Validate and store a DM submission.

    Returns {'ok': True, 'first_name', 'interests', 'committees'} on
    success, or {'ok': False, 'error', 'first_name', 'interests',
    'committees'} so the caller can re-render the form with picks intact.
    """
    picked_interests = _selected(
        state_values, "volunteer_interests_block", "volunteer_interests_input")
    picked_committees = _selected(
        state_values, "volunteer_committees_block", "volunteer_committees_input")

    slack_user = SlackUser.query.filter_by(slack_uid=slack_uid).one_or_none()
    user = (User.query.filter_by(slack_user_id=slack_user.id).one_or_none()
            if slack_user else None)
    us = (UserSeason.get_for_user_season(user.id, season_id)
          if user else None)
    if us is None:
        current_app.logger.warning(
            "Volunteer submit from %s has no registration for season %s",
            slack_uid, season_id)
        return {"ok": False,
                "error": "We couldn't find your registration. "
                         "Message an organizer and we'll sort it out.",
                "first_name": user.first_name if user else "there",
                "interests": picked_interests,
                "committees": picked_committees}

    interests, committees, errors = validate_volunteer_selections(
        picked_interests, picked_committees)
    if errors:
        return {"ok": False, "error": errors[0],
                "first_name": user.first_name,
                "interests": picked_interests,
                "committees": picked_committees}

    us.volunteer_interests = interests
    us.volunteer_committees = committees
    db.session.commit()
    return {"ok": True, "first_name": user.first_name,
            "interests": interests, "committees": committees}
