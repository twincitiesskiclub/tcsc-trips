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
