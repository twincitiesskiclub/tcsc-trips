"""Slack user sync service - synchronizes Slack workspace members with database."""
from dataclasses import dataclass
from flask import current_app

from app.models import db, SlackUser, User
from app.slack.client import fetch_workspace_members


@dataclass
class SyncResult:
    """Result of a Slack user sync operation."""
    slack_users_created: int = 0
    slack_users_updated: int = 0
    users_matched: int = 0
    unmatched_slack_users: int = 0
    unmatched_db_users: int = 0
    skipped_bots: int = 0
    skipped_no_email: int = 0
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self):
        return {
            'slack_users_created': self.slack_users_created,
            'slack_users_updated': self.slack_users_updated,
            'users_matched': self.users_matched,
            'unmatched_slack_users': self.unmatched_slack_users,
            'unmatched_db_users': self.unmatched_db_users,
            'skipped_bots': self.skipped_bots,
            'skipped_no_email': self.skipped_no_email,
            'errors': self.errors,
        }


def sync_slack_users() -> SyncResult:
    """
    Sync Slack workspace members to the database.

    1. Fetches all Slack workspace members via API
    2. Creates or updates SlackUser records (keyed by slack_uid)
    3. Auto-matches to User records by email where possible
    4. Returns sync statistics

    Note: Does not delete SlackUser records for removed Slack members,
    just updates their 'deleted' status field.
    """
    result = SyncResult()

    try:
        members = fetch_workspace_members()
    except Exception as e:
        result.errors.append(f"Failed to fetch Slack members: {str(e)}")
        return result

    for member in members:
        slack_uid = member['slack_uid']
        email = member.get('email')

        # Skip bots
        if member.get('is_bot'):
            result.skipped_bots += 1
            continue

        # Skip members without email (can't match)
        if not email:
            result.skipped_no_email += 1
            continue

        # Find or create SlackUser record
        slack_user = SlackUser.query.filter_by(slack_uid=slack_uid).first()

        if slack_user:
            # Update existing record
            slack_user.display_name = member.get('display_name')
            slack_user.full_name = member.get('full_name')
            slack_user.email = email
            slack_user.title = member.get('title')
            slack_user.phone = member.get('phone')
            slack_user.status = member.get('status')
            slack_user.timezone = member.get('timezone')
            result.slack_users_updated += 1
        else:
            # Create new record
            slack_user = SlackUser(
                slack_uid=slack_uid,
                display_name=member.get('display_name'),
                full_name=member.get('full_name'),
                email=email,
                title=member.get('title'),
                phone=member.get('phone'),
                status=member.get('status'),
                timezone=member.get('timezone'),
            )
            db.session.add(slack_user)
            db.session.flush()  # Ensure slack_user.id is assigned before FK reference
            result.slack_users_created += 1

        # Try to auto-match to User by email if not already linked
        # Use case-insensitive email matching
        if not slack_user.user:
            user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if user and not user.slack_user_id:
                user.slack_user_id = slack_user.id
                result.users_matched += 1
                current_app.logger.info(f"Auto-matched User {user.email} to Slack {slack_uid}")

    db.session.commit()

    # Calculate unmatched counts
    result.unmatched_slack_users = SlackUser.query.outerjoin(User).filter(User.id.is_(None)).count()
    result.unmatched_db_users = User.query.filter(User.slack_user_id.is_(None)).count()

    return result


def get_sync_status() -> dict:
    """Get current sync status and statistics."""
    total_slack_users = SlackUser.query.count()
    total_db_users = User.query.count()
    matched_users = User.query.filter(User.slack_user_id.isnot(None)).count()
    unmatched_slack = SlackUser.query.outerjoin(User).filter(User.id.is_(None)).count()
    unmatched_db = User.query.filter(User.slack_user_id.is_(None)).count()

    return {
        'total_slack_users': total_slack_users,
        'total_db_users': total_db_users,
        'matched_users': matched_users,
        'unmatched_slack_users': unmatched_slack,
        'unmatched_db_users': unmatched_db,
    }


def get_unmatched_slack_users() -> list[dict]:
    """Get SlackUser records not linked to any User."""
    slack_users = SlackUser.query.outerjoin(User).filter(User.id.is_(None)).all()
    return [
        {
            'id': su.id,
            'slack_uid': su.slack_uid,
            'email': su.email,
            'display_name': su.display_name,
            'full_name': su.full_name,
        }
        for su in slack_users
    ]


def get_unmatched_db_users() -> list[dict]:
    """Get User records not linked to any SlackUser."""
    users = User.query.filter(User.slack_user_id.is_(None)).all()
    return [
        {
            'id': u.id,
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'full_name': u.full_name,
            'status': u.status,
        }
        for u in users
    ]


def get_all_users_with_slack_status() -> list[dict]:
    """Get all User records with their Slack correlation status."""
    users = User.query.outerjoin(SlackUser).all()
    return [
        {
            'id': u.id,
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'full_name': u.full_name,
            'status': u.status,
            'slack_matched': u.slack_user_id is not None,
            'slack_uid': u.slack_user.slack_uid if u.slack_user else None,
            'slack_display_name': u.slack_user.display_name if u.slack_user else None,
        }
        for u in users
    ]


def link_user_to_slack(user_id: int, slack_user_id: int) -> bool:
    """
    Manually link a User to a SlackUser.

    Returns True if successful, False if user/slack_user not found or already linked.
    """
    user = User.query.get(user_id)
    slack_user = SlackUser.query.get(slack_user_id)

    if not user or not slack_user:
        return False

    # Check if SlackUser is already linked to another user
    if slack_user.user and slack_user.user.id != user_id:
        current_app.logger.warning(
            f"SlackUser {slack_user_id} already linked to User {slack_user.user.id}"
        )
        return False

    user.slack_user_id = slack_user_id
    db.session.commit()

    current_app.logger.info(f"Manually linked User {user.email} to SlackUser {slack_user.slack_uid}")
    return True


def unlink_user_from_slack(user_id: int) -> bool:
    """
    Remove Slack association from a User.

    Returns True if successful, False if user not found.
    """
    user = User.query.get(user_id)
    if not user:
        return False

    if user.slack_user_id:
        current_app.logger.info(f"Unlinked User {user.email} from Slack")
        user.slack_user_id = None
        db.session.commit()

    return True
