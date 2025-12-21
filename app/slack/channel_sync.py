"""Slack channel membership sync service.

This module handles automated synchronization of Slack workspace memberships
based on database user status. It processes users through three tiers:

- full_member (ACTIVE): Full workspace access, 12 channels
- multi_channel_guest (ALUMNI, 1 season): MCG with 10 channels
- single_channel_guest (ALUMNI, 2+ seasons): SCG with 1 channel

The sync also handles:
- Reactivating deactivated users
- Inviting new members not yet in Slack
- Preserving full members' manually-joined public channels
- Exception users (admins, board members, coaches)
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional
from flask import current_app

from app.models import User, Tag, db
from app.constants import UserStatus
from app.slack.client import (
    get_team_id,
    get_channel_maps,
    get_user_channels,
    add_user_to_channel,
    remove_user_from_channel,
    fetch_all_slack_users,
)
from app.slack.admin_api import (
    ROLE_FULL_MEMBER,
    ROLE_MCG,
    ROLE_SCG,
    change_user_role,
    invite_user_by_email,
    validate_admin_credentials,
    CookieExpiredError,
    AdminAPIError,
)


@dataclass
class ChannelSyncResult:
    """Result of a channel sync operation."""
    total_processed: int = 0
    reactivated_users: int = 0
    role_changes: int = 0
    channel_adds: int = 0
    channel_removals: int = 0
    invites_sent: int = 0
    users_skipped: int = 0
    errors: list = field(default_factory=list)
    dry_run: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'total_processed': self.total_processed,
            'reactivated_users': self.reactivated_users,
            'role_changes': self.role_changes,
            'channel_adds': self.channel_adds,
            'channel_removals': self.channel_removals,
            'invites_sent': self.invites_sent,
            'users_skipped': self.users_skipped,
            'errors': self.errors,
            'dry_run': self.dry_run,
        }


def load_channel_config() -> dict:
    """Load channel configuration from YAML file.

    Returns:
        Config dict with channels, exception_tags, expertvoice settings, etc.

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config',
        'slack_channels.yaml'
    )

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_db_email_to_tier() -> dict[str, str]:
    """Build a map of user email -> Slack tier from the database.

    Uses User.get_slack_tier() to determine each user's tier based on
    their status and seasons_since_active.

    Returns:
        Dict mapping lowercase email -> tier string
        ('full_member', 'multi_channel_guest', 'single_channel_guest', or None)
    """
    email_to_tier = {}

    # Get all users with email addresses
    users = User.query.filter(User.email.isnot(None)).all()

    for user in users:
        tier = user.get_slack_tier()
        if tier and user.email:
            email_to_tier[user.email.lower()] = tier

    current_app.logger.info(
        f"Built tier map: {len(email_to_tier)} users with tiers "
        f"(full_member: {sum(1 for t in email_to_tier.values() if t == 'full_member')}, "
        f"multi_channel_guest: {sum(1 for t in email_to_tier.values() if t == 'multi_channel_guest')}, "
        f"single_channel_guest: {sum(1 for t in email_to_tier.values() if t == 'single_channel_guest')})"
    )

    return email_to_tier


def get_exception_emails(config: dict) -> set[str]:
    """Get emails of users who should be skipped by automation.

    Exception users include:
    - Users with exception Tags (BOARD_MEMBER, COACH, ADMIN, LEAD)
    - Slack admins, owners, and bots (checked separately during sync)

    Args:
        config: Channel config dict with exception_tags list

    Returns:
        Set of lowercase email addresses
    """
    exception_tags = config.get('exception_tags', [])

    if not exception_tags:
        return set()

    # Query users with any of the exception tags
    exception_users = User.query.join(User.tags).filter(
        Tag.name.in_(exception_tags)
    ).all()

    exception_emails = {u.email.lower() for u in exception_users if u.email}

    current_app.logger.info(
        f"Found {len(exception_emails)} exception users with tags: {exception_tags}"
    )

    return exception_emails


def determine_tier_for_slack_user(
    slack_email: str,
    db_email_to_tier: dict[str, str]
) -> str:
    """Determine the target tier for a Slack user.

    Args:
        slack_email: User's email from Slack
        db_email_to_tier: Map of email -> tier from database

    Returns:
        Tier string. If user is not in database, returns 'single_channel_guest'
        (treating unknown users as "Other Members")
    """
    if not slack_email:
        return 'single_channel_guest'

    return db_email_to_tier.get(slack_email.lower(), 'single_channel_guest')


def is_slack_exception_user(slack_user: dict, exception_emails: set[str]) -> bool:
    """Check if a Slack user should be skipped.

    Args:
        slack_user: Raw Slack user dict
        exception_emails: Set of exception user emails

    Returns:
        True if user should be skipped
    """
    # Skip Slack admins, owners, and bots
    if slack_user.get('is_admin') or slack_user.get('is_owner') or slack_user.get('is_bot'):
        return True

    # Check email against exception list
    email = slack_user.get('profile', {}).get('email', '').lower()
    return email in exception_emails


def get_target_channel_ids(
    tier: str,
    config: dict,
    channel_name_to_id: dict[str, str]
) -> set[str]:
    """Get the target channel IDs for a tier.

    Args:
        tier: Tier string ('full_member', 'multi_channel_guest', 'single_channel_guest')
        config: Channel config dict
        channel_name_to_id: Map of channel name -> ID

    Returns:
        Set of channel IDs
    """
    channel_names = config.get('channels', {}).get(tier, [])
    channel_ids = set()

    for name in channel_names:
        channel_id = channel_name_to_id.get(name)
        if channel_id:
            channel_ids.add(channel_id)
        else:
            current_app.logger.warning(f"Channel '{name}' not found in workspace")

    return channel_ids


def get_role_for_tier(tier: str) -> str:
    """Map tier to Slack role constant.

    Args:
        tier: Tier string

    Returns:
        Role constant (ROLE_FULL_MEMBER, ROLE_MCG, or ROLE_SCG)
    """
    if tier == 'full_member':
        return ROLE_FULL_MEMBER
    elif tier == 'multi_channel_guest':
        return ROLE_MCG
    else:
        return ROLE_SCG


def needs_role_change(slack_user: dict, target_tier: str) -> bool:
    """Check if a user needs a role change.

    Args:
        slack_user: Raw Slack user dict
        target_tier: Target tier string

    Returns:
        True if role change is needed
    """
    is_restricted = slack_user.get('is_restricted', False)
    is_ultra_restricted = slack_user.get('is_ultra_restricted', False)

    if target_tier == 'full_member':
        # Need to promote if currently a guest
        return is_restricted or is_ultra_restricted
    elif target_tier == 'multi_channel_guest':
        # Need to set MCG if not currently MCG
        is_mcg = is_restricted and not is_ultra_restricted
        return not is_mcg
    else:  # single_channel_guest
        # Need to set SCG if not currently SCG
        return not is_ultra_restricted


def sync_single_user(
    slack_user: dict,
    target_tier: str,
    target_channel_ids: set[str],
    channel_id_to_properties: dict[str, dict],
    team_id: str,
    dry_run: bool,
    result: ChannelSyncResult
) -> None:
    """Sync a single user's role and channel memberships.

    Handles:
    - Reactivation of deactivated users
    - Role changes (Full Member, MCG, SCG)
    - Channel additions and removals
    - Full member public channel preservation

    Args:
        slack_user: Raw Slack user dict
        target_tier: Target tier string
        target_channel_ids: Set of target channel IDs for this tier
        channel_id_to_properties: Map of channel ID -> properties
        team_id: Slack team ID
        dry_run: If True, only log what would be done
        result: ChannelSyncResult to update
    """
    user_id = slack_user['id']
    email = slack_user.get('profile', {}).get('email', '')
    user_str = f"{email} ({user_id})" if email else user_id

    target_role = get_role_for_tier(target_tier)

    try:
        # Handle deactivated users - reactivate with correct role
        if slack_user.get('deleted'):
            current_app.logger.info(f"Reactivating deactivated user {user_str} as {target_tier}")
            change_user_role(
                user_id=user_id,
                email=email,
                target_role=target_role,
                team_id=team_id,
                dry_run=dry_run,
                channel_ids=list(target_channel_ids)
            )
            result.reactivated_users += 1
            result.role_changes += 1
            return  # Reactivation handles channels, done

        # Get current channels
        try:
            current_channels = get_user_channels(user_id)
        except Exception as e:
            current_app.logger.error(f"Error fetching channels for {user_str}: {e}")
            current_channels = set()
            result.errors.append(f"Failed to fetch channels for {user_str}: {e}")

        # Check if role change is needed
        role_change_needed = needs_role_change(slack_user, target_tier)

        if role_change_needed:
            current_app.logger.info(f"Changing {user_str} to {target_tier}")

            # For MCG/SCG, role change also sets channels
            if target_tier in ('multi_channel_guest', 'single_channel_guest'):
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=target_role,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(target_channel_ids)
                )
                result.role_changes += 1
                return  # MCG/SCG role change handles channels

            else:
                # Full member - just set role, then sync channels separately
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=target_role,
                    team_id=team_id,
                    dry_run=dry_run
                )
                result.role_changes += 1

        # Sync channels for full members (or when role didn't change)
        # For MCG/SCG, the role change API handles channels

        if target_tier == 'full_member':
            # Add user to target channels they're not in
            channels_to_add = target_channel_ids - current_channels
            for channel_id in channels_to_add:
                if add_user_to_channel(user_id, channel_id, email, dry_run):
                    result.channel_adds += 1

            # Remove from channels not in target list
            # BUT preserve public channels full members joined manually
            channels_to_remove = current_channels - target_channel_ids
            for channel_id in channels_to_remove:
                channel_props = channel_id_to_properties.get(channel_id, {})
                if channel_props.get('is_public', False):
                    # Skip removal - let full members stay in public channels
                    current_app.logger.debug(
                        f"Preserving {user_str} in public channel {channel_props.get('name', channel_id)}"
                    )
                    continue

                if remove_user_from_channel(user_id, channel_id, email, dry_run):
                    result.channel_removals += 1

    except CookieExpiredError as e:
        current_app.logger.error(f"Cookie expired during sync for {user_str}: {e}")
        result.errors.append(f"Cookie expired: {e}")
        raise  # Re-raise to stop the sync

    except AdminAPIError as e:
        current_app.logger.error(f"Admin API error for {user_str}: {e}")
        result.errors.append(f"Admin API error for {user_str}: {e}")

    except Exception as e:
        current_app.logger.error(f"Unexpected error syncing {user_str}: {e}")
        result.errors.append(f"Error syncing {user_str}: {e}")


def invite_new_members(
    db_email_to_tier: dict[str, str],
    slack_emails: set[str],
    exception_emails: set[str],
    target_channel_ids: list[str],
    team_id: str,
    invitation_message: str,
    dry_run: bool,
    result: ChannelSyncResult
) -> None:
    """Invite database users who aren't in Slack yet.

    Only invites ACTIVE users (full_member tier) who:
    - Have an email in the database
    - Are not already in Slack
    - Are not exception users

    Args:
        db_email_to_tier: Map of email -> tier from database
        slack_emails: Set of emails already in Slack
        exception_emails: Set of exception user emails
        target_channel_ids: Channel IDs to add new users to
        team_id: Slack team ID
        invitation_message: Welcome message for invites
        dry_run: If True, only log what would be done
        result: ChannelSyncResult to update
    """
    # Get ACTIVE users (full_member tier) not in Slack
    to_invite = []
    for email, tier in db_email_to_tier.items():
        if tier == 'full_member' and email not in slack_emails and email not in exception_emails:
            to_invite.append(email)

    if not to_invite:
        current_app.logger.info("No new members to invite")
        return

    current_app.logger.info(f"Inviting {len(to_invite)} new members to Slack")

    for email in to_invite:
        try:
            invite_user_by_email(
                email=email,
                channel_ids=target_channel_ids,
                team_id=team_id,
                message=invitation_message,
                dry_run=dry_run
            )
            result.invites_sent += 1
        except (CookieExpiredError, AdminAPIError) as e:
            current_app.logger.error(f"Failed to invite {email}: {e}")
            result.errors.append(f"Failed to invite {email}: {e}")


def run_channel_sync(dry_run: Optional[bool] = None) -> ChannelSyncResult:
    """Run the full channel sync process.

    This is the main entry point for the channel sync job.

    Process:
    1. Load config (use config dry_run if not overridden)
    2. Validate admin credentials
    3. Fetch all Slack users and channels
    4. Build tier map from database
    5. Sync each Slack user's role and channels
    6. Invite new members not in Slack
    7. Return result stats

    Args:
        dry_run: Override config dry_run setting. If None, uses config value.

    Returns:
        ChannelSyncResult with stats and any errors
    """
    result = ChannelSyncResult()

    # Load config
    try:
        config = load_channel_config()
    except Exception as e:
        current_app.logger.error(f"Failed to load channel config: {e}")
        result.errors.append(f"Config load failed: {e}")
        return result

    # Determine dry_run mode
    if dry_run is None:
        dry_run = config.get('dry_run', True)
    result.dry_run = dry_run

    mode_str = "[DRY RUN]" if dry_run else "[LIVE]"
    current_app.logger.info(f"{mode_str} Starting channel sync")

    # Validate admin credentials
    is_valid, error_msg = validate_admin_credentials()
    if not is_valid:
        current_app.logger.error(f"Admin credentials invalid: {error_msg}")
        result.errors.append(f"Credentials invalid: {error_msg}")
        return result

    try:
        # Get team ID
        team_id = get_team_id()
        current_app.logger.info(f"Team ID: {team_id}")

        # Get channel maps
        channel_name_to_id, channel_id_to_properties = get_channel_maps()

        # Build tier map from database
        db_email_to_tier = get_db_email_to_tier()

        # Get exception emails
        exception_emails = get_exception_emails(config)

        # Fetch all Slack users
        slack_users = fetch_all_slack_users()
        slack_emails = {
            u.get('profile', {}).get('email', '').lower()
            for u in slack_users
            if u.get('profile', {}).get('email')
        }

        # Pre-compute target channel IDs for each tier
        tier_channel_ids = {
            tier: get_target_channel_ids(tier, config, channel_name_to_id)
            for tier in ['full_member', 'multi_channel_guest', 'single_channel_guest']
        }

        # Process each Slack user
        for slack_user in slack_users:
            email = slack_user.get('profile', {}).get('email', '').lower()
            user_id = slack_user['id']

            # Skip exception users
            if is_slack_exception_user(slack_user, exception_emails):
                result.users_skipped += 1
                continue

            # Skip users without email
            if not email:
                current_app.logger.debug(f"Skipping user {user_id} - no email")
                result.users_skipped += 1
                continue

            result.total_processed += 1

            # Determine target tier
            target_tier = determine_tier_for_slack_user(email, db_email_to_tier)
            target_channel_ids = tier_channel_ids[target_tier]

            # Sync this user
            sync_single_user(
                slack_user=slack_user,
                target_tier=target_tier,
                target_channel_ids=target_channel_ids,
                channel_id_to_properties=channel_id_to_properties,
                team_id=team_id,
                dry_run=dry_run,
                result=result
            )

        # Invite new members
        invitation_message = config.get('invitation_message', 'Welcome to the Slack workspace!')
        full_member_channels = list(tier_channel_ids['full_member'])

        invite_new_members(
            db_email_to_tier=db_email_to_tier,
            slack_emails=slack_emails,
            exception_emails=exception_emails,
            target_channel_ids=full_member_channels,
            team_id=team_id,
            invitation_message=invitation_message,
            dry_run=dry_run,
            result=result
        )

    except CookieExpiredError as e:
        current_app.logger.error(f"Sync aborted - cookies expired: {e}")
        result.errors.append(f"Sync aborted - cookies expired: {e}")

    except Exception as e:
        current_app.logger.error(f"Sync failed with unexpected error: {e}")
        result.errors.append(f"Sync failed: {e}")

    # Log summary
    current_app.logger.info(
        f"{mode_str} Channel sync complete: "
        f"processed={result.total_processed}, "
        f"role_changes={result.role_changes}, "
        f"reactivated={result.reactivated_users}, "
        f"channel_adds={result.channel_adds}, "
        f"channel_removals={result.channel_removals}, "
        f"invites={result.invites_sent}, "
        f"skipped={result.users_skipped}, "
        f"errors={len(result.errors)}"
    )

    return result
