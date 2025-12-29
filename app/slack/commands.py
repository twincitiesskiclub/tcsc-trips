"""Slack slash command handlers for /tcsc command."""

from datetime import datetime, timedelta
from flask import current_app
from app.models import db, User
from app.practices.models import Practice, PracticeRSVP, PracticeLead
from app.practices.interfaces import RSVPStatus


def handle_tcsc_command(command_text: str, user_id: str, user_name: str) -> dict:
    """Handle /tcsc slash command.

    Args:
        command_text: Command arguments after /tcsc
        user_id: Slack user ID
        user_name: Slack username

    Returns:
        dict with keys:
        - response_type: 'ephemeral' or 'in_channel'
        - text: Response text (plain or markdown)
    """
    # Parse subcommand
    parts = command_text.strip().split()
    subcommand = parts[0].lower() if parts else 'help'

    if subcommand == 'practice':
        return _handle_practice_command(user_id)

    elif subcommand == 'rsvp':
        if len(parts) < 3:
            return {
                'response_type': 'ephemeral',
                'text': 'Usage: `/tcsc rsvp <practice_id> <going|not_going|maybe>`'
            }
        try:
            practice_id = int(parts[1])
            status = parts[2].lower()
            return _handle_rsvp_command(practice_id, status, user_id, user_name)
        except ValueError:
            return {
                'response_type': 'ephemeral',
                'text': 'Invalid practice ID. Must be a number.'
            }

    elif subcommand == 'status':
        return _handle_status_command(user_id)

    elif subcommand == 'help':
        return _handle_help_command()

    else:
        return {
            'response_type': 'ephemeral',
            'text': f'Unknown command: `{subcommand}`. Use `/tcsc help` to see available commands.'
        }


def _handle_practice_command(user_id: str) -> dict:
    """Show today's and upcoming practices.

    Args:
        user_id: Slack user ID

    Returns:
        Slack response dict
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today_start + timedelta(days=7)

    # Get upcoming practices
    practices = Practice.query.filter(
        Practice.date >= today_start,
        Practice.date < week_end,
        Practice.status != 'cancelled'
    ).order_by(Practice.date).all()

    if not practices:
        return {
            'response_type': 'ephemeral',
            'text': 'No practices scheduled in the next 7 days.'
        }

    # Build response
    response_lines = ['*Upcoming Practices:*\n']

    for practice in practices:
        date_str = practice.date.strftime('%a %b %d at %I:%M %p')
        location = practice.location.name if practice.location else 'TBD'

        practice_line = f"• *{date_str}* at {location}"

        # Add activities
        if practice.activities:
            activity_names = ', '.join([a.name for a in practice.activities])
            practice_line += f"\n  Activities: {activity_names}"

        # Add leaders
        if practice.leads:
            lead_names = []
            for lead in practice.leads:
                if lead.person:
                    name = lead.person.short_name or 'Unknown'
                    if lead.person.slack_user_id:
                        name = f"<@{lead.person.slack_user_id}>"
                    lead_names.append(name)
            if lead_names:
                practice_line += f"\n  Leaders: {', '.join(lead_names)}"

        # Check user's RSVP
        rsvp = PracticeRSVP.query.filter_by(
            practice_id=practice.id,
            slack_user_id=user_id
        ).first()

        if rsvp:
            status_emoji = {
                'going': ':white_check_mark:',
                'not_going': ':x:',
                'maybe': ':grey_question:'
            }.get(rsvp.status, '')
            practice_line += f"\n  Your RSVP: {status_emoji} {rsvp.status.replace('_', ' ').title()}"

        response_lines.append(practice_line)
        response_lines.append('')  # Blank line

    return {
        'response_type': 'ephemeral',
        'text': '\n'.join(response_lines)
    }


def _handle_rsvp_command(practice_id: int, status: str, user_id: str, user_name: str) -> dict:
    """Quick RSVP to a practice.

    Args:
        practice_id: Practice ID
        status: 'going', 'not_going', or 'maybe'
        user_id: Slack user ID
        user_name: Slack username

    Returns:
        Slack response dict
    """
    # Validate status
    valid_statuses = ['going', 'not_going', 'maybe']
    if status not in valid_statuses:
        return {
            'response_type': 'ephemeral',
            'text': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
        }

    # Find practice
    practice = Practice.query.get(practice_id)
    if not practice:
        return {
            'response_type': 'ephemeral',
            'text': f'Practice #{practice_id} not found.'
        }

    # Find user linked to this Slack ID
    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()

    if not user:
        return {
            'response_type': 'ephemeral',
            'text': 'Your Slack account is not linked to a TCSC membership. Please contact an admin to link your account.'
        }

    # Create or update RSVP
    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice_id,
        user_id=user.id
    ).first()

    if rsvp:
        rsvp.status = status
        rsvp.responded_at = datetime.utcnow()
        action = 'updated'
    else:
        rsvp = PracticeRSVP(
            practice_id=practice_id,
            user_id=user.id,
            status=status,
            slack_user_id=user_id,
            responded_at=datetime.utcnow()
        )
        db.session.add(rsvp)
        action = 'recorded'

    db.session.commit()

    status_emoji = {
        'going': ':white_check_mark:',
        'not_going': ':x:',
        'maybe': ':grey_question:'
    }.get(status, '')

    date_str = practice.date.strftime('%a %b %d at %I:%M %p')

    return {
        'response_type': 'ephemeral',
        'text': f'{status_emoji} RSVP {action}! You\'re {status.replace("_", " ")} for practice on {date_str}.'
    }


def _handle_status_command(user_id: str) -> dict:
    """Show user's upcoming RSVPs and lead assignments.

    Args:
        user_id: Slack user ID

    Returns:
        Slack response dict
    """
    # Find user
    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()

    if not user:
        return {
            'response_type': 'ephemeral',
            'text': 'No account found. RSVP to a practice to create one!'
        }

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get upcoming RSVPs
    rsvps = PracticeRSVP.query.join(Practice).filter(
        PracticeRSVP.user_id == user.id,
        Practice.date >= today_start,
        Practice.status != 'cancelled'
    ).order_by(Practice.date).all()

    # Get lead assignments
    lead_assignments = PracticeLead.query.join(Practice).filter(
        PracticeLead.user_id == user.id,
        Practice.date >= today_start,
        Practice.status != 'cancelled'
    ).order_by(Practice.date).all()

    # Build response
    response_lines = ['*Your Practice Status:*\n']

    if lead_assignments:
        response_lines.append('*Lead Assignments:*')
        for assignment in lead_assignments:
            practice = assignment.practice
            date_str = practice.date.strftime('%a %b %d at %I:%M %p')
            location = practice.location.name if practice.location else 'TBD'
            confirmed = ':white_check_mark:' if assignment.confirmed else ':question:'
            response_lines.append(
                f"• {confirmed} *{date_str}* at {location} ({assignment.role.upper()})"
            )
        response_lines.append('')

    if rsvps:
        response_lines.append('*RSVPs:*')
        for rsvp in rsvps:
            practice = rsvp.practice
            date_str = practice.date.strftime('%a %b %d at %I:%M %p')
            location = practice.location.name if practice.location else 'TBD'

            status_emoji = {
                'going': ':white_check_mark:',
                'not_going': ':x:',
                'maybe': ':grey_question:'
            }.get(rsvp.status, '')

            response_lines.append(
                f"• {status_emoji} *{date_str}* at {location} - {rsvp.status.replace('_', ' ').title()}"
            )
        response_lines.append('')

    if not lead_assignments and not rsvps:
        response_lines.append('No upcoming practices or RSVPs.')

    return {
        'response_type': 'ephemeral',
        'text': '\n'.join(response_lines)
    }


def _handle_help_command() -> dict:
    """Show help text for /tcsc command.

    Returns:
        Slack response dict
    """
    help_text = """*TCSC Practice Commands*

`/tcsc practice` - Show upcoming practices for the next 7 days

`/tcsc rsvp <practice_id> <going|not_going|maybe>` - Quick RSVP to a practice
Example: `/tcsc rsvp 42 going`

`/tcsc status` - Show your upcoming RSVPs and lead assignments

`/tcsc help` - Show this help message
"""

    return {
        'response_type': 'ephemeral',
        'text': help_text
    }
