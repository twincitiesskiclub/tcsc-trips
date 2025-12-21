"""Slack user sync service - synchronizes Slack workspace members with database."""
from dataclasses import dataclass
from flask import current_app

from datetime import date

from app.models import db, SlackUser, User, Season, UserSeason
from app.slack.client import fetch_workspace_members
from app.constants import UserStatus, UserSeasonStatus


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
    skipped_deactivated: int = 0
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
            'skipped_deactivated': self.skipped_deactivated,
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

        # Skip deactivated Slack users (email starts with "deactivateduser")
        if email.lower().startswith('deactivateduser'):
            result.skipped_deactivated += 1
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
        # Exclude DROPPED users - they lost lottery and won't have Slack access
        if not slack_user.user:
            user = User.query.filter(
                db.func.lower(User.email) == email.lower(),
                User.status != UserStatus.DROPPED
            ).first()
            if user and not user.slack_user_id:
                user.slack_user_id = slack_user.id
                result.users_matched += 1
                current_app.logger.info(f"Auto-matched User {user.email} to Slack {slack_uid}")

    db.session.commit()

    # Calculate unmatched counts (exclude DROPPED users from DB count)
    result.unmatched_slack_users = SlackUser.query.outerjoin(User).filter(User.id.is_(None)).count()
    result.unmatched_db_users = User.query.filter(
        User.slack_user_id.is_(None),
        User.status != UserStatus.DROPPED
    ).count()

    return result


def get_sync_status() -> dict:
    """Get current sync status and statistics.

    Excludes DROPPED users from DB counts since they won't have Slack access.
    """
    total_slack_users = SlackUser.query.count()
    # Exclude DROPPED users from all DB-side counts
    total_db_users = User.query.filter(User.status != UserStatus.DROPPED).count()
    matched_users = User.query.filter(
        User.slack_user_id.isnot(None),
        User.status != UserStatus.DROPPED
    ).count()
    unmatched_slack = SlackUser.query.outerjoin(User).filter(User.id.is_(None)).count()
    unmatched_db = User.query.filter(
        User.slack_user_id.is_(None),
        User.status != UserStatus.DROPPED
    ).count()

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
    """Get User records not linked to any SlackUser.

    Excludes DROPPED users since they won't have Slack access.
    """
    users = User.query.filter(
        User.slack_user_id.is_(None),
        User.status != UserStatus.DROPPED
    ).all()
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
    """Get all User records with their Slack correlation status.

    Excludes DROPPED users since they won't have Slack access.
    """
    users = User.query.filter(User.status != UserStatus.DROPPED).outerjoin(SlackUser).all()
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

    Also updates the User's email to match the Slack email (Slack is authoritative).

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

    # Update email to match Slack (Slack email is authoritative)
    if slack_user.email and user.email != slack_user.email:
        current_app.logger.info(f"Updating User email from {user.email} to {slack_user.email}")
        user.email = slack_user.email

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


def import_slack_user(slack_user_id: int) -> dict:
    """
    Import an unmatched SlackUser as a new User with legacy season membership.

    Creates a User record from SlackUser data, assigns them to the legacy season
    with ACTIVE status, and links them to the SlackUser.

    Returns dict with 'success' bool and 'message' or 'user_id'.
    """
    slack_user = SlackUser.query.get(slack_user_id)
    if not slack_user:
        return {'success': False, 'message': 'SlackUser not found'}

    # Check if already linked
    if slack_user.user:
        return {'success': False, 'message': 'SlackUser already linked to a User'}

    # Check if email already exists in Users table
    existing_user = User.query.filter(db.func.lower(User.email) == slack_user.email.lower()).first()
    if existing_user:
        return {'success': False, 'message': f'User with email {slack_user.email} already exists'}

    # Parse name - split on first space, fallback to full string
    full_name = slack_user.full_name or slack_user.display_name or 'Unknown'
    name_parts = full_name.split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ''

    # Get or create legacy season
    legacy_season = Season.query.filter_by(name='Former Members (Legacy)').first()
    if not legacy_season:
        legacy_season = Season(
            name='Former Members (Legacy)',
            season_type='legacy',
            year=1900,
            start_date=date(1900, 1, 1),
            end_date=date(1900, 12, 31)
        )
        db.session.add(legacy_season)
        db.session.flush()

    # Create User
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=slack_user.email,
        phone=slack_user.phone,
        status=UserStatus.ALUMNI,
        slack_user_id=slack_user.id,
    )
    db.session.add(user)
    db.session.flush()

    # Create UserSeason for legacy season
    user_season = UserSeason(
        user_id=user.id,
        season_id=legacy_season.id,
        registration_type='returning',
        registration_date=date(1900, 1, 1),
        status=UserSeasonStatus.ACTIVE
    )
    db.session.add(user_season)
    db.session.commit()

    current_app.logger.info(f"Imported SlackUser {slack_user.slack_uid} as User {user.id} ({user.email})")
    return {'success': True, 'user_id': user.id, 'message': f'Created user {user.full_name}'}
