"""Block Kit builders for trip registration surfaces. Pure functions."""
from app.slack.blocks.text import guard_slack_blocks, guard_fallback_text
from app.utils import format_datetime_central


def _money(cents):
    return f"${cents / 100:.2f}"


def build_trip_announcement_blocks(trip, series, spots_left=None,
                                   base_url="https://tcsc.ski"):
    price = (_money(trip.price_low) if trip.price_low == trip.price_high
             else f"{_money(trip.price_low)} to {_money(trip.price_high)}")
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": trip.name, "emoji": True}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Where:* {trip.destination}"},
            {"type": "mrkdwn", "text": f"*When:* {trip.formatted_date_range}"},
            {"type": "mrkdwn", "text": f"*Price:* {price}"},
            {"type": "mrkdwn",
             "text": ("*Signup closes:* "
                      f"{format_datetime_central(trip.signup_end)}")},
        ]},
        {"type": "actions", "elements": [
            {"type": "button",
             "text": {"type": "plain_text", "text": "Sign up", "emoji": True},
             "style": "primary",
             "url": f"{base_url}/{series.slug}/register"},
        ]},
    ]
    if spots_left is not None:
        blocks.insert(2, {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"{spots_left} spots left"}]})
    return guard_slack_blocks(blocks, surface="trip_announcement")


def trip_announcement_fallback(trip):
    return guard_fallback_text(
        f"{trip.name} - {trip.formatted_date_range} - sign up now",
        surface="trip_announcement")


def _answer_fields(registration):
    fields = []
    for key, value in (registration.answers or {}).items():
        rendered = ", ".join(value) if isinstance(value, list) else str(value)
        fields.append({"type": "mrkdwn", "text": f"*{key}:* {rendered}"})
    return fields[:10]  # Slack caps section fields


def build_registration_dm_blocks(registration, trip, series):
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":ski: *You're signed up for {trip.name}!*\n"
            f"A hold of {_money(registration.amount_cents)} is on your card. "
            "You'll only be charged when the roster is confirmed.")}},
    ]
    fields = _answer_fields(registration)
    if fields:
        blocks.append({"type": "section", "fields": fields})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": (
        "We'll DM you when you're confirmed. Questions? Ask in the trip "
        "channel.")}]})
    return guard_slack_blocks(blocks, surface="trip_registration_dm")


def registration_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're signed up for {trip.name} - hold placed, charge on "
        "roster confirmation.", surface="trip_registration_dm")


def build_confirmation_dm_blocks(registration, trip, series):
    channel_note = (f"You've been added to #{series.slack_channel_name}."
                    if series.slack_channel_name else "")
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":tada: *You're confirmed for {trip.name}!*\n"
            f"Your card was charged {_money(registration.amount_cents)}. "
            f"{channel_note}")}},
    ]
    return guard_slack_blocks(blocks, surface="trip_confirmation_dm")


def confirmation_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're confirmed for {trip.name} - card charged.",
        surface="trip_confirmation_dm")
