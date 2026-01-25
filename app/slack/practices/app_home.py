"""App Home view operations."""

from datetime import datetime
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client
from app.slack.blocks import build_app_home_blocks
from app.practices.models import Practice


def publish_app_home(user_slack_id: str) -> dict:
    """Publish the App Home view for a user.

    Args:
        user_slack_id: Slack user ID

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    from datetime import timedelta
    from app.practices.models import PracticeRSVP, PracticeLead
    from app.models import User

    client = get_slack_client()

    # Get upcoming practices (next 14 days)
    now = datetime.utcnow()
    end_date = now + timedelta(days=14)

    practices = Practice.query.filter(
        Practice.date >= now,
        Practice.date <= end_date
    ).order_by(Practice.date).all()

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Get user's RSVPs
    user_rsvps = {}
    user_lead_practices = []

    # Find user by slack ID
    user = User.query.join(User.slack_user).filter_by(slack_uid=user_slack_id).first()

    if user:
        # Get user's RSVPs for these practices
        practice_ids = [p.id for p in practices]
        rsvps = PracticeRSVP.query.filter(
            PracticeRSVP.practice_id.in_(practice_ids),
            PracticeRSVP.user_id == user.id
        ).all()

        for rsvp in rsvps:
            user_rsvps[rsvp.practice_id] = rsvp.status

        # Get user's lead assignments
        lead_assignments = PracticeLead.query.filter(
            PracticeLead.practice_id.in_(practice_ids),
            PracticeLead.user_id == user.id
        ).all()
        user_lead_practices = [la.practice_id for la in lead_assignments]

    # Build blocks
    blocks = build_app_home_blocks(practice_infos, user_rsvps, user_lead_practices)

    try:
        client.views_publish(
            user_id=user_slack_id,
            view={
                "type": "home",
                "blocks": blocks
            }
        )

        current_app.logger.info(f"Published app home for user {user_slack_id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error publishing app home: {error_msg}")
        return {'success': False, 'error': error_msg}
