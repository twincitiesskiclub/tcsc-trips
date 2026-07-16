"""One-shot recovery after an ambiguous practice delete commit."""

from collections.abc import Mapping

from app.models import db
from app.practices.models import Practice
from app.slack.practices.announcements import (
    post_practice_announcement,
    update_practice_slack_post,
)
from app.slack.practices.refresh import (
    refresh_registered_practice_summaries,
)


def _require_successful_details(result):
    if result.get("success") is not True or "details" not in result:
        return result

    details = result["details"]
    if isinstance(details, Mapping) and details.get("success") is True:
        return result

    if isinstance(details, Mapping):
        error = "Practice announcement Details recovery failed"
        if details.get("error"):
            error = f"{error}: {details['error']}"
    else:
        error = (
            "Practice announcement Details recovery returned an invalid result"
        )
    return {**result, "success": False, "error": error}


def _repost_to_original_channel(practice, original_channel_id):
    result = _require_successful_details(
        post_practice_announcement(
            practice,
            channel_id_override=original_channel_id,
            create_log_thread=False,
        )
    )
    if result.get("success") is True:
        return {**result, "action": "reposted"}
    return result


def _restore_practice_announcement(
    practice,
    *,
    original_channel_id,
    original_message_ts,
):
    """Restore one practice root without duplicating or splitting a root."""
    if not original_message_ts:
        return {"success": True, "action": "not_posted"}
    if not original_channel_id:
        return {
            "success": False,
            "error": "Original Slack channel is missing",
        }

    original_siblings = Practice.query.filter_by(
        slack_channel_id=original_channel_id,
        slack_message_ts=original_message_ts,
    ).filter(Practice.id != practice.id).all()
    shared = bool(original_siblings) or bool(practice.slack_session_emoji)
    current_is_original = (
        practice.slack_channel_id == original_channel_id
        and practice.slack_message_ts == original_message_ts
    )

    if current_is_original:
        result = _require_successful_details(
            update_practice_slack_post(practice)
        )
        if result.get("success") is True:
            return {**result, "action": "rebuilt"}
        if result.get("error") == "message_not_found" and not shared:
            practice.slack_channel_id = None
            practice.slack_message_ts = None
            practice.slack_details_ts = None
            return _repost_to_original_channel(practice, original_channel_id)
        return result

    identity_is_cleared = (
        not practice.slack_channel_id and not practice.slack_message_ts
    )
    if identity_is_cleared:
        if shared:
            return {
                "success": False,
                "error": (
                    "Original Slack root is shared; refusing to split it"
                ),
            }
        return _repost_to_original_channel(practice, original_channel_id)

    return {
        "success": False,
        "error": "Practice Slack identity changed during delete recovery",
    }


def _incomplete(*, error, announcement=None, summaries=None):
    return {
        "success": False,
        "outcome": "incomplete",
        "practice_deleted": False,
        "practice_restored": False,
        "recovery_incomplete": True,
        "announcement": announcement,
        "summaries": summaries,
        "error": error,
    }


def _summary_result_is_healthy(result):
    return isinstance(result, dict) and (
        result.get("success") is True or result.get("skipped") == "absent"
    )


def _summaries_are_healthy(summaries):
    return bool(summaries) and all(
        _summary_result_is_healthy(result) for result in summaries.values()
    )


def _summary_error(summaries):
    if not isinstance(summaries, dict):
        return "Practice summary recovery returned an invalid result"
    if summaries.get("error"):
        return str(summaries["error"])

    failures = []
    for surface, result in summaries.items():
        if _summary_result_is_healthy(result):
            continue
        if isinstance(result, dict) and result.get("error"):
            failures.append(f"{surface}: {result['error']}")
        else:
            failures.append(f"{surface}: unsuccessful")
    return "; ".join(failures) or "Practice summary recovery failed"


def recover_failed_practice_delete(
    practice_id,
    *,
    original_channel_id,
    original_message_ts,
    original_week_start,
):
    """Repair Slack surfaces once after an uncertain database delete."""
    try:
        db.session.rollback()
        practice = db.session.get(
            Practice,
            practice_id,
            populate_existing=True,
        )
    except Exception as exc:
        return _incomplete(error=f"Could not reload practice: {exc}")

    if practice is None:
        return {
            "success": True,
            "outcome": "deleted",
            "practice_deleted": True,
        }

    try:
        announcement = _restore_practice_announcement(
            practice,
            original_channel_id=original_channel_id,
            original_message_ts=original_message_ts,
        )
    except Exception as exc:
        announcement = {
            "success": False,
            "error": f"Could not restore practice announcement: {exc}",
        }

    try:
        summaries = refresh_registered_practice_summaries(
            original_week_start,
            exclude_practice_id=None,
        )
    except Exception as exc:
        summaries = {
            "success": False,
            "error": f"Could not refresh practice summaries: {exc}",
        }

    errors = []
    if announcement.get("success") is not True:
        errors.append(
            announcement.get("error")
            or "Practice announcement recovery failed"
        )
    if not _summaries_are_healthy(summaries):
        errors.append(_summary_error(summaries))
    if errors:
        return _incomplete(
            error="; ".join(errors),
            announcement=announcement,
            summaries=summaries,
        )

    return {
        "success": True,
        "outcome": "restored",
        "practice_deleted": False,
        "practice_restored": True,
        "announcement": announcement,
        "summaries": summaries,
    }
