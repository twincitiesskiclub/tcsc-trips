import os
import requests
from flask import current_app


def send_payment_notification(name, amount_cents, email, payment_intent_id):
    """Send Slack notification for successful payment."""
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

    if not slack_webhook_url:
        current_app.logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
        return False

    amount_dollars = amount_cents / 100
    message = {
        "text": (
            f"New Stripe payment received!\n"
            f"Description:\n"
            f"Customer Name: {name}\n"
            f"Amount: {amount_dollars}\n"
            f"Email: {email}\n"
            f"Payment ID: {payment_intent_id}"
        )
    }

    try:
        response = requests.post(slack_webhook_url, json=message, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send Slack notification: {e}")
        return False


TIER_DISPLAY = {
    'full_member': 'Full Member',
    'multi_channel_guest': 'MCG',
    'single_channel_guest': 'SCG',
}


def send_tier_transition_notification(name, email, from_tier, to_tier, reason):
    """Per-transition notification. Gated by notify_per_transition config flag.

    The caller is responsible for honoring the flag; this function always sends
    when called. Use send_sync_summary_notification for default per-run output.
    """
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

    if not slack_webhook_url:
        current_app.logger.warning("SLACK_WEBHOOK_URL not configured, skipping tier notification")
        return False

    from_display = TIER_DISPLAY.get(from_tier, from_tier)
    to_display = TIER_DISPLAY.get(to_tier, to_tier)

    message = {
        "text": (
            f"Slack tier change: {name} ({email})\n"
            f"{from_display} → {to_display}\n"
            f"Reason: {reason}"
        )
    }

    try:
        response = requests.post(slack_webhook_url, json=message, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send tier transition notification: {e}")
        return False


def send_sync_summary_notification(result, dry_run=False):
    """End-of-sync summary. Always sent.

    Args:
        result: ChannelSyncResult with populated counters
        dry_run: whether this sync was a dry-run
    """
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

    if not slack_webhook_url:
        current_app.logger.warning("SLACK_WEBHOOK_URL not configured, skipping sync summary")
        return False

    mode = "DRY RUN" if dry_run else "live"
    lines = [
        f"Channel sync complete ({mode}):",
        f"• Role changes: {result.role_changes}",
        f"• Channel additions: {result.channel_adds}",
        f"• Channel removals: {result.channel_removals}",
        f"• Invites: {result.invites_sent}",
        f"• Errors: {len(result.errors)}",
    ]

    message = {"text": "\n".join(lines)}

    try:
        response = requests.post(slack_webhook_url, json=message, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send sync summary notification: {e}")
        return False
