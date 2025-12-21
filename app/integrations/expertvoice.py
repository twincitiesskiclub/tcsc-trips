"""ExpertVoice SFTP sync for member pro deals access.

ExpertVoice provides pro deals access to club members. We sync a CSV file
of eligible members via SFTP. Eligibility:
- ACTIVE members (current season)
- ALUMNI members with seasons_since_active == 1 (skipped one season)

Members who have been inactive for 2+ seasons are NOT eligible.

Required environment variables:
- EXPERTVOICE_SFTP_USERNAME
- EXPERTVOICE_SFTP_PASSWORD
"""
import os
import csv
import tempfile
from dataclasses import dataclass, field
from typing import Optional

import paramiko
import yaml
from flask import current_app

from app.models import db, User
from app.constants import UserStatus


@dataclass
class ExpertVoiceSyncResult:
    """Result of an ExpertVoice sync operation."""
    members_synced: int = 0
    active_members: int = 0
    alumni_members: int = 0
    uploaded: bool = False
    dry_run: bool = True
    errors: list = field(default_factory=list)


def load_expertvoice_config() -> dict:
    """Load ExpertVoice configuration from slack_channels.yaml.

    Returns:
        Dict with enabled flag and SFTP settings.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If expertvoice config is missing.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config', 'slack_channels.yaml'
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    if 'expertvoice' not in config:
        raise ValueError("expertvoice section missing from config")

    return config['expertvoice']


def get_sftp_credentials() -> tuple[str, str]:
    """Get SFTP credentials from environment.

    Returns:
        Tuple of (username, password).

    Raises:
        ValueError: If credentials are missing.
    """
    username = os.environ.get('EXPERTVOICE_SFTP_USERNAME')
    password = os.environ.get('EXPERTVOICE_SFTP_PASSWORD')

    missing = []
    if not username:
        missing.append('EXPERTVOICE_SFTP_USERNAME')
    if not password:
        missing.append('EXPERTVOICE_SFTP_PASSWORD')

    if missing:
        raise ValueError(f"Missing required SFTP credentials: {', '.join(missing)}")

    return username, password


def get_eligible_members() -> list[User]:
    """Query database for ExpertVoice-eligible members.

    Eligibility:
    - ACTIVE status (current season members)
    - ALUMNI status with seasons_since_active == 1 (one season gap)

    Returns:
        List of User objects eligible for ExpertVoice access.
    """
    return User.query.filter(
        db.or_(
            User.status == UserStatus.ACTIVE,
            db.and_(
                User.status == UserStatus.ALUMNI,
                User.seasons_since_active == 1
            )
        )
    ).all()


def generate_csv(members: list[User], output_path: str) -> None:
    """Generate ExpertVoice CSV file.

    Format: EmployeeID,FirstName,LastName
    - EmployeeID is the member's email (unique identifier)
    - FirstName and LastName from User model

    Args:
        members: List of User objects to include.
        output_path: Path to write CSV file.
    """
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Header row
        writer.writerow(['EmployeeID', 'FirstName', 'LastName'])

        for member in members:
            writer.writerow([
                member.email,
                member.first_name,
                member.last_name
            ])

    current_app.logger.info(f"Generated ExpertVoice CSV with {len(members)} members at {output_path}")


def upload_csv(file_path: str, config: dict, dry_run: bool = False) -> None:
    """Upload CSV to ExpertVoice SFTP server.

    Args:
        file_path: Path to the CSV file to upload.
        config: ExpertVoice config dict with sftp settings.
        dry_run: If True, only log what would be done.

    Raises:
        ValueError: If SFTP credentials are missing.
        paramiko.SSHException: On SSH/SFTP errors.
    """
    sftp_config = config['sftp']
    host = sftp_config['host']
    port = sftp_config.get('port', 22)
    remote_path = sftp_config['path']
    filename = sftp_config['filename']

    if dry_run:
        current_app.logger.info(
            f"[DRY RUN] Would upload {file_path} to {host}:{remote_path}{filename}"
        )
        return

    username, password = get_sftp_credentials()

    ssh_client = None
    sftp_client = None

    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        current_app.logger.info(f"Connecting to ExpertVoice SFTP at {host}:{port}")

        ssh_client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False
        )

        sftp_client = ssh_client.open_sftp()
        sftp_client.chdir(remote_path)

        remote_file = filename
        sftp_client.put(file_path, remote_file)

        current_app.logger.info(f"Successfully uploaded {filename} to ExpertVoice SFTP")

    except paramiko.AuthenticationException as e:
        current_app.logger.error(f"SFTP authentication failed: {e}")
        raise
    except paramiko.SSHException as e:
        current_app.logger.error(f"SSH error during SFTP upload: {e}")
        raise
    except Exception as e:
        current_app.logger.error(f"Error uploading to ExpertVoice SFTP: {e}")
        raise
    finally:
        if sftp_client:
            sftp_client.close()
        if ssh_client:
            ssh_client.close()


def sync_expertvoice(dry_run: Optional[bool] = None) -> ExpertVoiceSyncResult:
    """Sync eligible members to ExpertVoice via SFTP.

    This is the main entry point for the ExpertVoice sync job.

    Args:
        dry_run: Override config dry_run setting. If None, uses config value.

    Returns:
        ExpertVoiceSyncResult with sync statistics.
    """
    result = ExpertVoiceSyncResult()

    try:
        # Load config
        config = load_expertvoice_config()

        if not config.get('enabled', True):
            current_app.logger.info("ExpertVoice sync is disabled in config")
            return result

        # Determine dry_run mode
        if dry_run is None:
            # Load from main config file
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'slack_channels.yaml'
            )
            with open(config_path, 'r') as f:
                main_config = yaml.safe_load(f)
            dry_run = main_config.get('dry_run', True)

        result.dry_run = dry_run

        if dry_run:
            current_app.logger.info("[DRY RUN] Starting ExpertVoice sync")
        else:
            current_app.logger.info("Starting ExpertVoice sync")

        # Get eligible members from database
        members = get_eligible_members()

        if not members:
            current_app.logger.info("No eligible members found for ExpertVoice sync")
            return result

        # Count by status
        for member in members:
            if member.status == UserStatus.ACTIVE:
                result.active_members += 1
            else:
                result.alumni_members += 1

        result.members_synced = len(members)

        current_app.logger.info(
            f"Found {result.members_synced} eligible members "
            f"({result.active_members} ACTIVE, {result.alumni_members} ALUMNI)"
        )

        # Generate CSV in temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
            temp_path = tmp.name

        try:
            generate_csv(members, temp_path)

            # Upload to SFTP
            upload_csv(temp_path, config, dry_run)
            result.uploaded = not dry_run

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        if dry_run:
            current_app.logger.info(
                f"[DRY RUN] ExpertVoice sync complete: "
                f"{result.members_synced} members would be synced"
            )
        else:
            current_app.logger.info(
                f"ExpertVoice sync complete: {result.members_synced} members synced"
            )

        return result

    except FileNotFoundError as e:
        error_msg = f"Config file not found: {e}"
        current_app.logger.error(error_msg)
        result.errors.append(error_msg)
        return result

    except ValueError as e:
        error_msg = f"Configuration error: {e}"
        current_app.logger.error(error_msg)
        result.errors.append(error_msg)
        return result

    except Exception as e:
        error_msg = f"ExpertVoice sync failed: {e}"
        current_app.logger.error(error_msg)
        result.errors.append(error_msg)
        return result
