"""Cookie-based Slack admin APIs for role management.

These APIs are undocumented and require browser cookies for authentication.
They are used for operations not available in the official Slack API:
- Setting users to Full Member / Multi-Channel Guest / Single-Channel Guest
- Inviting users to the workspace
- Reactivating deactivated users

Credentials required (set via environment variables):
- SLACK_ADMIN_TOKEN: Admin user token (xoxs-...)
- SLACK_YOUR_COOKIE: Browser session cookie (d=xoxd-...)
- SLACK_YOUR_X_ID: Browser x-id value
"""
import os
import time
import functools
import requests
from typing import Optional
from flask import current_app


# Role constants
ROLE_FULL_MEMBER = "FULL_MEMBER"
ROLE_MCG = "MCG"  # Multi-Channel Guest
ROLE_SCG = "SCG"  # Single-Channel Guest


class AdminAPIError(Exception):
    """Exception raised for admin API errors."""
    pass


class CookieExpiredError(AdminAPIError):
    """Exception raised when browser cookies have expired."""
    pass


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0):
    """Decorator for retrying API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for wait time between retries
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        current_app.logger.warning(
                            f"Request failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator


def get_admin_credentials() -> dict:
    """Get admin API credentials from environment.

    Returns:
        Dict with token, cookie, x_id, and headers/params needed for requests.

    Raises:
        ValueError: If required credentials are missing.
    """
    token = os.environ.get('SLACK_ADMIN_TOKEN')
    cookie = os.environ.get('SLACK_YOUR_COOKIE')
    x_id = os.environ.get('SLACK_YOUR_X_ID')

    missing = []
    if not token:
        missing.append('SLACK_ADMIN_TOKEN')
    if not cookie:
        missing.append('SLACK_YOUR_COOKIE')
    if not x_id:
        missing.append('SLACK_YOUR_X_ID')

    if missing:
        raise ValueError(f"Missing required admin credentials: {', '.join(missing)}")

    base_url = "https://twincitiesskiclub.slack.com/api/"

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Origin': 'https://twincitiesskiclub.slack.com',
        'Cookie': cookie,
    }

    common_params = {
        '_x_id': x_id,
        'slack_route': 'T02J2AVLSCT',  # TCSC workspace ID
        '_x_version_ts': 'noversion',
        'fp': '32',
        '_x_num_retries': '0',
    }

    return {
        'token': token,
        'cookie': cookie,
        'x_id': x_id,
        'base_url': base_url,
        'headers': headers,
        'common_params': common_params,
    }


def validate_admin_credentials() -> tuple[bool, Optional[str]]:
    """Test admin API credentials by making a lightweight request.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, "error description").
    """
    try:
        creds = get_admin_credentials()
    except ValueError as e:
        return False, str(e)

    try:
        # Make a lightweight request to test credentials
        # Using team.info as a simple test endpoint
        url = creds['base_url'] + 'team.info'
        headers = creds['headers'].copy()
        headers.pop('Content-Type', None)

        data = {'token': creds['token']}
        files = {key: (None, str(value)) for key, value in data.items()}

        response = requests.post(
            url,
            headers=headers,
            params=creds['common_params'],
            files=files,
            timeout=10
        )

        result = response.json()

        if result.get('ok'):
            return True, None

        error = result.get('error', 'Unknown error')
        if error in ('invalid_auth', 'not_authed', 'token_revoked', 'account_inactive'):
            return False, f"Cookie expired or invalid: {error}"

        return False, f"API error: {error}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


@retry_with_backoff(max_retries=3)
def make_admin_request(
    api_method: str,
    data: dict,
    action_description: str,
    email: str,
    user_id: Optional[str] = None,
    dry_run: bool = False
) -> dict:
    """Make an authenticated request to the Slack admin API.

    Args:
        api_method: The API method to call (e.g., 'users.admin.setRegular')
        data: Request data dict
        action_description: Human-readable description for logging
        email: User email for logging
        user_id: Optional user ID for logging
        dry_run: If True, only log what would be done

    Returns:
        Response data dict

    Raises:
        CookieExpiredError: If authentication failed (cookies expired)
        AdminAPIError: For other API errors
    """
    if dry_run:
        user_str = f"{email} ({user_id})" if user_id else email
        current_app.logger.info(f"[DRY RUN] Would {action_description.lower()} for {user_str}")
        return {'ok': True, 'dry_run': True}

    creds = get_admin_credentials()
    url = creds['base_url'] + api_method

    headers = creds['headers'].copy()
    headers.pop('Content-Type', None)

    # Convert data to multipart form
    files = {key: (None, str(value)) for key, value in data.items()}

    try:
        response = requests.post(
            url,
            headers=headers,
            params=creds['common_params'],
            files=files,
            timeout=30
        )
        response_data = response.json()

        user_str = f"{email} ({user_id})" if user_id else email

        if response.status_code == 200 and response_data.get('ok'):
            current_app.logger.info(f"{action_description} for {user_str}")
            return response_data

        error_msg = response_data.get('error', 'Unknown error')

        # Check for auth errors (cookie expiration)
        if error_msg in ('invalid_auth', 'not_authed', 'token_revoked', 'account_inactive'):
            current_app.logger.error(
                f"Cookie expired or invalid when trying to {action_description.lower()} "
                f"for {user_str}: {error_msg}"
            )
            raise CookieExpiredError(f"Admin API authentication failed: {error_msg}")

        current_app.logger.error(f"Error {action_description.lower()} for {user_str}: {error_msg}")
        raise AdminAPIError(f"Admin API request failed: {error_msg}")

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"HTTP request failed for {email}: {e}")
        raise


def change_user_role(
    user_id: str,
    email: str,
    target_role: str,
    team_id: str,
    dry_run: bool,
    channel_ids: Optional[list[str]] = None
) -> None:
    """Change a user's role in Slack.

    This function handles:
    - Setting user to Full Member (removes guest restrictions)
    - Setting user to Multi-Channel Guest (MCG) with specific channel access
    - Setting user to Single-Channel Guest (SCG) with single channel access
    - Reactivating deactivated users with the appropriate role

    Args:
        user_id: Slack user ID
        email: User's email (for logging)
        target_role: ROLE_FULL_MEMBER, ROLE_MCG, or ROLE_SCG
        team_id: Slack team/workspace ID
        dry_run: If True, only log what would be done
        channel_ids: Required for MCG (list of channels) and SCG (single channel)

    Raises:
        ValueError: If target_role is invalid or channel_ids missing when required
        CookieExpiredError: If authentication failed
        AdminAPIError: For other API errors
    """
    creds = get_admin_credentials()

    action_description = f"Set to {target_role}"
    if channel_ids:
        action_description += f" with channels: {', '.join(channel_ids[:3])}{'...' if len(channel_ids) > 3 else ''}"

    data = {
        'token': creds['token'],
        'user': user_id,
        '_x_mode': 'online',
    }

    if target_role == ROLE_FULL_MEMBER:
        api_method = 'users.admin.setRegular'
        data['_x_reason'] = 'admin_script_set_regular'
        data['team_id'] = team_id

    elif target_role == ROLE_MCG:
        if not channel_ids:
            raise ValueError(f"channel_ids required when setting user to {ROLE_MCG}")
        api_method = 'users.admin.setRestricted'
        data['channels'] = ','.join(channel_ids)
        data['target_team'] = team_id
        data['_x_reason'] = 'admin_script_set_mcg'

    elif target_role == ROLE_SCG:
        if not channel_ids or len(channel_ids) < 1:
            raise ValueError(f"At least one channel_id required when setting user to {ROLE_SCG}")
        api_method = 'users.admin.setUltraRestricted'
        data['channel'] = channel_ids[0]  # SCG only gets one channel
        data['_x_reason'] = 'admin_script_set_scg'

    else:
        raise ValueError(f"Invalid target_role: {target_role}")

    make_admin_request(api_method, data, action_description, email, user_id, dry_run)


def invite_user_by_email(
    email: str,
    channel_ids: list[str],
    team_id: str,
    message: str,
    dry_run: bool = False
) -> None:
    """Invite a new user to the Slack workspace.

    Args:
        email: Email address to invite
        channel_ids: List of channel IDs to add user to initially
        team_id: Slack team/workspace ID
        message: Welcome message for the invitation
        dry_run: If True, only log what would be done

    Raises:
        CookieExpiredError: If authentication failed
        AdminAPIError: For other API errors
    """
    creds = get_admin_credentials()

    channel_ids_str = ','.join(channel_ids) if channel_ids else ''

    data = {
        'token': creds['token'],
        'invites': f'[{{"email":"{email}","type":"regular","mode":"manual"}}]',
        'source': 'invite_modal',
        'campaign': 'team_site_admin',
        'mode': 'manual',
        'restricted': 'false',
        'ultra_restricted': 'false',
        'email_password_policy_enabled': 'false',
        'team_id': team_id,
        'extra_message': message,
        '_x_reason': 'invite_bulk',
        '_x_mode': 'online',
    }

    if channel_ids_str:
        data['channel_ids'] = channel_ids_str

    action_description = f"Invite to workspace"
    if channel_ids:
        action_description += f" with {len(channel_ids)} initial channels"

    make_admin_request('users.admin.inviteBulk', data, action_description, email, dry_run=dry_run)
