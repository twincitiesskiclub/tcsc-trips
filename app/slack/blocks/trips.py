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


def _answer_fields(registration, trip):
    question_labels = {
        question["key"]: question["label"]
        for question in (trip.custom_questions or [])
        if "builtin" not in question
    }
    fields = []
    for key, value in (registration.answers or {}).items():
        rendered = ", ".join(value) if isinstance(value, list) else str(value)
        label = question_labels.get(key, key)
        fields.append({"type": "mrkdwn", "text": f"*{label}:* {rendered}"})
    return fields[:10]  # Slack caps section fields


def build_registration_dm_blocks(registration, trip, series):
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":ski: *You're signed up for {trip.name}!*\n"
            f"A hold of {_money(registration.amount_cents)} is on your card. "
            "You'll only be charged when the roster is confirmed.")}},
    ]
    fields = _answer_fields(registration, trip)
    if fields:
        blocks.append({"type": "section", "fields": fields})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": (
        "We'll DM you when the roster is confirmed.")}]})
    return guard_slack_blocks(blocks, surface="trip_registration_dm")


def registration_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're signed up for {trip.name} - hold placed, charge on "
        "roster confirmation.", surface="trip_registration_dm")


def build_confirmation_dm_blocks(registration, trip, series):
    channel_note = (
        f" You've been added to #{series.slack_channel_name}."
        if series and series.slack_channel_name else ""
    )
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f":tada: *You're confirmed for {trip.name}!*\n"
            f"Your card was charged {_money(registration.amount_cents)}."
            f"{channel_note}")}},
    ]
    return guard_slack_blocks(blocks, surface="trip_confirmation_dm")


def confirmation_dm_fallback(registration, trip):
    return guard_fallback_text(
        f"You're confirmed for {trip.name} - card charged.",
        surface="trip_confirmation_dm")


# --- trip scholarships ------------------------------------------------------

MITCHELL_SLACK_UID = "U045LF8PCSW"
SCHOLARSHIP_CLOSE_FMT = "%a %b %-d, %-I:%M %p"


def _dollars(cents):
    return f"${cents // 100}" if cents % 100 == 0 else _money(cents)


def build_scholarship_offer_blocks(scholarship):
    amount = _dollars(scholarship.amount_cents)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"Hi {scholarship.user.first_name}, you're getting a TCSC trip "
            f"scholarship: {amount} off one trip this season, thanks to our "
            "sponsors Twin Cities Orthopedics and Kwik Trip. Tap the button "
            f"to get your code. Questions? Ask <@{MITCHELL_SLACK_UID}>.")}},
        {"type": "actions", "elements": [
            {"type": "button", "action_id": "trip_scholarship_reveal",
             "value": str(scholarship.id), "style": "primary",
             "text": {"type": "plain_text", "text": "Get my code"}},
        ]},
    ]
    return guard_slack_blocks(blocks, surface="trip_scholarship")


def scholarship_offer_fallback(scholarship):
    return guard_fallback_text(
        f"You're getting a {_dollars(scholarship.amount_cents)} TCSC trip "
        "scholarship. Open this message to get your code.",
        surface="trip_scholarship")


def build_scholarship_revealed_blocks(scholarship, applied_registration,
                                      open_trips, base_url):
    amount = _dollars(scholarship.amount_cents)
    if applied_registration is not None:
        how = (f"Already applied to {applied_registration.trip.name}: we'll "
               f"take {amount} off when your spot is confirmed.")
    else:
        how = ("Enter it in the Scholarship code box when you register for a "
               f"trip at tcsc.ski. It takes {amount} off either price and only "
               "works for you. If you aren't picked in a trip lottery, the "
               "code comes back for another trip.")
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"Your code: *{scholarship.code}*\n{how}")}},
    ]
    if open_trips:
        lines = [
            f"<{base_url}/{trip.series.slug}/register|{trip.name}> "
            "(registration closes "
            f"{format_datetime_central(trip.signup_end, SCHOLARSHIP_CLOSE_FMT)})"
            for trip in open_trips
        ]
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": "Open now: " + ", ".join(lines)}]})
    return guard_slack_blocks(blocks, surface="trip_scholarship")


def scholarship_revealed_fallback(scholarship):
    return guard_fallback_text(
        f"Your TCSC trip scholarship code: {scholarship.code}",
        surface="trip_scholarship")
