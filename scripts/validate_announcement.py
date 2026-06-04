"""Live validation harness for the redesigned practice announcement.

Posts a matrix of scenarios to the UNUSED test channel C07G9RTMRT3 so the UI
can be reviewed on real mobile + desktop Slack. NEVER targets the real
#announcements-practices. Run teardown to delete what it posted.

Usage:
    python scripts/validate_announcement.py post      # post all scenarios
    python scripts/validate_announcement.py teardown  # delete posted messages
"""
import json
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

from app import create_app
from app.slack.client import get_slack_client
from app.slack.blocks.announcements import (
    build_practice_announcement_blocks, build_practice_details_blocks,
)

TEST_CHANNEL = "C07G9RTMRT3"
POSTED_FILE = "validate_posted_ts.json"


def _act(name, gear=None):
    return SimpleNamespace(name=name, gear_required=gear)


def _loc():
    return SimpleNamespace(name="Theodore Wirth", spot="Trailhead",
        address="1301 Theodore Wirth Pkwy", google_maps_url="https://maps.example/wirth",
        latitude=44.99, longitude=-93.32, parking_notes="Chalet lot; arrive 15 min early.",
        social_location=SimpleNamespace(name="Utepils Brewing", google_maps_url=None))


def _weather(**o):
    base = dict(temperature_f=25, feels_like_f=18, conditions_summary="cloudy, light snow",
                wind_speed_mph=12, wind_direction="NW", alerts=[])
    base.update(o)
    return SimpleNamespace(**base)


def _daylight(central_hour=16, central_minute=38):
    """Build a DaylightInfo-like stub whose sunset is stored as naive UTC,
    matching production (app/integrations/daylight.py stores naive UTC).

    `central_hour`/`central_minute` is the desired sunset in Central wall-clock
    time; in winter (CST, UTC-6) that means UTC = Central + 6h. Mirrors the
    test fixture in tests/slack/test_announcement_blocks.py exactly.
    """
    sunset_utc = datetime(2026, 12, 29, central_hour, central_minute) + timedelta(hours=6)
    return SimpleNamespace(sunset=sunset_utc, civil_twilight_end=sunset_utc + timedelta(hours=1))


def _practice(**o):
    base = dict(
        date=datetime(2026, 12, 29, 12, 0),
        activities=[_act("Classic Ski", ["Classic skis", "kick wax"])],
        practice_types=[SimpleNamespace(name="Intervals")],
        location=_loc(),
        social_location=SimpleNamespace(name="Utepils Brewing", google_maps_url=None),
        workout_description="5 x 4min @ threshold, 2min easy between. Smooth weight transfer, complete kick.",
        logistics_notes="Meet at the trailhead flagpole. Cold out, warm up 15+ min.",
        has_social=True,
        leads=[SimpleNamespace(role=SimpleNamespace(name="COACH"), slack_user_id=None, display_name="Anders")],
    )
    base.update(o)
    return SimpleNamespace(**base)


# Scenario: (practice, weather, daylight, air_quality)
# after_dark: practice starts at 5 PM Central, sunset at 4:38 PM Central -> headlamp fires.
SCENARIOS = {
    "1_baseline": (
        _practice(),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
    "2_minimal": (
        _practice(logistics_notes=None, has_social=False, leads=[],
                  practice_types=[], workout_description="Easy distance ski, your choice of loop."),
        None,
        None,
        None,
    ),
    "3_multi_activity": (
        _practice(activities=[_act("Classic Ski"), _act("Skate Ski")]),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
    "4_no_activity": (
        _practice(activities=[]),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
    "6_after_dark": (
        # 5 PM Central start; sunset 4:38 PM Central -> headlamp line fires.
        _practice(date=datetime(2026, 12, 29, 17, 0)),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
    "7_high_aqi": (
        _practice(),
        _weather(conditions_summary="hazy"),
        _daylight(central_hour=16, central_minute=38),
        78,
    ),
    "8_clean_air": (
        _practice(),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        42,
    ),
    "9_alert": (
        _practice(),
        _weather(alerts=[SimpleNamespace(headline="Wind Chill Advisory")]),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
    "11_long": (
        _practice(logistics_notes="L " * 120, workout_description="W " * 120),
        _weather(),
        _daylight(central_hour=16, central_minute=38),
        38,
    ),
}


def post():
    client = get_slack_client()
    posted = []
    for name, (p, w, d, aqi) in SCENARIOS.items():
        hero = build_practice_announcement_blocks(p)
        r = client.chat_postMessage(
            channel=TEST_CHANNEL, blocks=hero, text=f"[{name}] hero",
            unfurl_links=False, unfurl_media=False,
        )
        ts = r["ts"]
        posted.append(ts)
        details = build_practice_details_blocks(p, weather=w, daylight=d, air_quality=aqi)
        if details:
            rr = client.chat_postMessage(
                channel=TEST_CHANNEL, thread_ts=ts, blocks=details,
                text=f"[{name}] details", reply_broadcast=False,
            )
            posted.append(rr["ts"])
        link = client.chat_getPermalink(channel=TEST_CHANNEL, message_ts=ts)["permalink"]
        print(f"{name}: {link}")
    with open(POSTED_FILE, "w") as f:
        json.dump(posted, f)
    print(f"\nPosted {len(SCENARIOS)} scenarios. Review on mobile + desktop, then run teardown.")


def teardown():
    client = get_slack_client()
    with open(POSTED_FILE) as f:
        for ts in json.load(f):
            try:
                client.chat_delete(channel=TEST_CHANNEL, ts=ts)
            except Exception as e:
                print(f"  could not delete {ts}: {e}")
    print("Teardown complete.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        cmd = sys.argv[1] if len(sys.argv) > 1 else "post"
        (post if cmd == "post" else teardown)()
