"""Guarded live review for final practice-announcement builders.

The harness uses synthetic records and the unused Slack channel C07G9RTMRT3.
It never queries or changes practice data. Run ``teardown`` after review.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from slack_sdk.errors import SlackApiError

from app import create_app
from app.practices.interfaces import AnnouncementConditions, PracticeStatus
from app.slack.blocks import (
    build_combined_fallback_text,
    build_combined_lift_blocks,
    build_practice_announcement_blocks,
    build_practice_details_blocks,
    build_practice_details_fallback_text,
    build_practice_fallback_text,
    build_weekly_summary_blocks,
    build_weekly_summary_fallback_text,
)
from app.slack.client import get_slack_client


logger = logging.getLogger(__name__)

TEST_CHANNEL = "C07G9RTMRT3"
STATE_FILE = Path(__file__).resolve().parents[1] / "validate_posted_ts.json"
MENTIONS = ("<!channel>", "<!here>", "<!everyone>")


@dataclass(frozen=True)
class Scenario:
    """One synthetic render through a final public builder family."""

    kind: str
    practices: tuple[SimpleNamespace, ...]
    conditions: AnnouncementConditions | None = None
    week_start: date | None = None
    weather_data: dict | None = None
    reaction_names: tuple[str, ...] = ()


def _activity(name, gear_required=None):
    return SimpleNamespace(
        id=1,
        name=name,
        gear_required=list(gear_required or []),
    )


def _location(**overrides):
    values = {
        "id": 1,
        "name": "Theodore Wirth",
        "spot": "Trailhead",
        "address": "1301 Theodore Wirth Pkwy",
        "google_maps_url": "https://maps.example/wirth",
        "latitude": 44.99,
        "longitude": -93.32,
        "parking_notes": "Chalet lot; arrive 15 minutes early.",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _weather(**overrides):
    values = {
        "temperature_f": 72,
        "feels_like_f": 72,
        "conditions_summary": "partly cloudy",
        "wind_speed_mph": 8,
        "wind_direction": "NW",
        "alerts": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _trail():
    return SimpleNamespace(
        ski_quality="good",
        groomed=True,
        report_url="https://trails.example/report",
    )


def _daylight(practice_date, sunset_hour=20, sunset_minute=59):
    local_sunset = practice_date.replace(
        hour=sunset_hour,
        minute=sunset_minute,
        tzinfo=ZoneInfo("America/Chicago"),
    )
    sunset = local_sunset.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return SimpleNamespace(
        sunset=sunset,
        civil_twilight_end=sunset + timedelta(hours=1),
    )


def _practice(practice_id, when, **overrides):
    values = {
        "id": practice_id,
        "date": when,
        "day_of_week": when.strftime("%A"),
        "status": PracticeStatus.SCHEDULED,
        "activities": [_activity("Run", ["Running shoes"])],
        "practice_types": [
            SimpleNamespace(id=1, name="Intervals", has_intervals=True)
        ],
        "location": _location(),
        "social_location": SimpleNamespace(
            id=1,
            name="Utepils Brewing",
            google_maps_url=None,
        ),
        "workout_description": (
            "5 x 4 minutes at threshold with 2 minutes easy between."
        ),
        "logistics_notes": "Meet at the trailhead flagpole.",
        "plan_reactions": [],
        "has_social": True,
        "is_dark_practice": False,
        "leads": [
            SimpleNamespace(
                role=SimpleNamespace(name="COACH"),
                slack_user_id=None,
                display_name="Anders",
            )
        ],
        "slack_session_emoji": None,
        "cancellation_reason": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _conditions(practice, **overrides):
    values = {
        "weather": _weather(),
        "daylight": _daylight(practice.date),
        "air_quality": 54,
        "trail_conditions": _trail(),
        "duration_minutes": 90,
    }
    values.update(overrides)
    return AnnouncementConditions(**values)


def _standalone(practice, conditions):
    plan_names = tuple(item["emoji"] for item in practice.plan_reactions)
    return Scenario(
        kind="standalone",
        practices=(practice,),
        conditions=conditions,
        reaction_names=("white_check_mark", *plan_names),
    )


def _combined(*practices):
    plan_names = tuple(
        item["emoji"] for item in practices[0].plan_reactions
    )
    return Scenario(
        kind="combined",
        practices=tuple(practices),
        reaction_names=(
            *(practice.slack_session_emoji for practice in practices),
            *plan_names,
        ),
    )


_routine = _practice(1, datetime(2026, 7, 13, 18, 0))
_july_daylight = _practice(2, datetime(2026, 7, 14, 18, 0))
_after_sunset = _practice(3, datetime(2026, 7, 15, 20, 0))
_weather_alert = _practice(4, datetime(2026, 7, 16, 18, 0))
_aqi_101 = _practice(5, datetime(2026, 7, 17, 18, 0))
_missing_workout = _practice(
    6,
    datetime(2026, 7, 18, 9, 0),
    workout_description=None,
)
_no_details = _practice(
    7,
    datetime(2026, 7, 19, 9, 0),
    activities=[_activity("Run")],
    location=_location(parking_notes=None),
)
_interval_evergreen = _practice(
    8,
    datetime(2026, 7, 20, 18, 0),
    plan_reactions=[{
        "emoji": "evergreen_tree",
        "label": "Endurance instead of intervals",
    }],
)
_multiple_plan = _practice(
    9,
    datetime(2026, 7, 21, 18, 0),
    plan_reactions=[
        {"emoji": "evergreen_tree", "label": "Endurance instead"},
        {"emoji": "athletic_shoe", "label": "Run option"},
    ],
)
_overridden_plan = _practice(
    10,
    datetime(2026, 7, 22, 18, 0),
    plan_reactions=[{
        "emoji": "hatching_chick",
        "label": "First practice support",
    }],
)
_empty_plan = _practice(
    11,
    datetime(2026, 7, 23, 18, 0),
    plan_reactions=[],
)
_long_boundaries = _practice(
    12,
    datetime(2026, 7, 24, 18, 0),
    activities=[_activity("Boundary activity " + ("A" * 180), ["G" * 800])],
    workout_description="W" * 2_500,
    logistics_notes="L" * 2_500,
)

_weekly_active = _practice(13, datetime(2026, 7, 27, 18, 0))
_weekly_cancelled = _practice(
    14,
    datetime(2026, 8, 2, 9, 0),
    status=PracticeStatus.CANCELLED,
    cancellation_reason="Heat warning",
)

_combined_plan = [{
    "emoji": "hatching_chick",
    "label": "First strength practice support",
}]
_combined_tuesday = _practice(
    15,
    datetime(2026, 7, 14, 18, 15),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    workout_description="3 x 8 strength circuit",
    logistics_notes="Bring indoor shoes.",
    plan_reactions=_combined_plan,
    slack_session_emoji="six",
)
_combined_wednesday = _practice(
    16,
    datetime(2026, 7, 15, 19, 15),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    workout_description="3 x 8 strength circuit",
    logistics_notes="Bring indoor shoes.",
    plan_reactions=_combined_plan,
    slack_session_emoji="seven",
)
_mixed_active = _practice(
    17,
    datetime(2026, 7, 16, 18, 15),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    plan_reactions=_combined_plan,
    slack_session_emoji="eight",
)
_mixed_cancelled = _practice(
    18,
    datetime(2026, 7, 17, 19, 15),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    plan_reactions=_combined_plan,
    slack_session_emoji="nine",
    status=PracticeStatus.CANCELLED,
    cancellation_reason="Facility closed",
)


SCENARIOS = {
    "routine": _standalone(_routine, _conditions(_routine)),
    "july_no_false_headlamp": _standalone(
        _july_daylight,
        _conditions(
            _july_daylight,
            daylight=_daylight(_july_daylight.date, 20, 59),
        ),
    ),
    "after_sunset": _standalone(
        _after_sunset,
        _conditions(
            _after_sunset,
            daylight=_daylight(_after_sunset.date, 20, 30),
        ),
    ),
    "weather_alert": _standalone(
        _weather_alert,
        _conditions(
            _weather_alert,
            weather=_weather(alerts=[SimpleNamespace(
                headline="Severe Thunderstorm Warning"
            )]),
        ),
    ),
    "aqi_101": _standalone(
        _aqi_101,
        _conditions(_aqi_101, air_quality=101),
    ),
    "missing_workout": _standalone(
        _missing_workout, _conditions(_missing_workout)
    ),
    "no_details": _standalone(_no_details, AnnouncementConditions()),
    "interval_evergreen": _standalone(
        _interval_evergreen, _conditions(_interval_evergreen)
    ),
    "multiple_plan_reactions": _standalone(
        _multiple_plan, _conditions(_multiple_plan)
    ),
    "overridden_plan": _standalone(
        _overridden_plan, _conditions(_overridden_plan)
    ),
    "empty_plan": _standalone(_empty_plan, _conditions(_empty_plan)),
    "long_boundaries": _standalone(
        _long_boundaries,
        _conditions(
            _long_boundaries,
            weather=_weather(conditions_summary="C" * 500),
        ),
    ),
    "weekly_cross_month_cancelled": Scenario(
        kind="weekly",
        practices=(_weekly_active, _weekly_cancelled),
        week_start=date(2026, 7, 27),
        weather_data={
            _weekly_active.id: {
                "temp_f": 78,
                "conditions": "partly cloudy",
            }
        },
    ),
    "combined_strength": _combined(
        _combined_tuesday, _combined_wednesday
    ),
    "combined_mixed_cancelled": _combined(
        _mixed_active, _mixed_cancelled
    ),
}


def build_scenario(name, scenario):
    """Render one registry entry through its final public builder family."""
    if scenario.kind == "standalone":
        practice = scenario.practices[0]
        conditions = scenario.conditions
        root_blocks = build_practice_announcement_blocks(practice, conditions)
        root_fallback = build_practice_fallback_text(practice, conditions)
        details_blocks = build_practice_details_blocks(practice, conditions)
        details = None
        if details_blocks:
            details = (
                details_blocks,
                build_practice_details_fallback_text(practice, conditions),
            )
        return root_blocks, root_fallback, details

    if scenario.kind == "weekly":
        kwargs = {
            "week_start": scenario.week_start,
            "weather_data": scenario.weather_data,
        }
        return (
            build_weekly_summary_blocks(scenario.practices, **kwargs),
            build_weekly_summary_fallback_text(scenario.practices, **kwargs),
            None,
        )

    if scenario.kind == "combined":
        return (
            build_combined_lift_blocks(scenario.practices),
            build_combined_fallback_text(scenario.practices),
            None,
        )

    raise ValueError(f"Unknown scenario kind {scenario.kind!r} for {name}")


def _sanitize_for_test(value):
    if isinstance(value, dict):
        return {key: _sanitize_for_test(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_test(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_test(item) for item in value)
    if isinstance(value, str):
        for mention in MENTIONS:
            value = value.replace(mention, "")
    return value


def _with_run_marker(blocks, run_id, scenario_name, *, details=False):
    suffix = " · Details" if details else ""
    marker = _sanitize_for_test(
        f"🧪 Harness · {run_id} · {scenario_name}{suffix}"
    )
    return [
        *blocks,
        {
            "type": "context",
            "elements": [{"type": "plain_text", "text": marker}],
        },
    ]


def _assert_test_channel(channel):
    if channel != TEST_CHANNEL:
        raise RuntimeError(
            f"Refusing live validation outside {TEST_CHANNEL}"
        )


def _write_state(state, path=STATE_FILE):
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _load_state(path=STATE_FILE):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _new_state():
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {"run_id": f"{started}-{uuid4().hex[:8]}", "records": []}


def _post_recorded(client, state, *, state_path=STATE_FILE, **kwargs):
    if "blocks" in kwargs:
        kwargs["blocks"] = _sanitize_for_test(kwargs["blocks"])
    kwargs["text"] = _sanitize_for_test(kwargs.get("text", ""))
    _assert_test_channel(kwargs.get("channel"))
    response = client.chat_postMessage(**kwargs)
    state["records"].append({
        "channel": kwargs["channel"],
        "ts": response["ts"],
        "thread_ts": kwargs.get("thread_ts"),
    })
    _write_state(state, state_path)
    return response


def _add_reaction(client, *, channel, timestamp, name):
    _assert_test_channel(channel)
    try:
        client.reactions_add(
            channel=channel,
            timestamp=timestamp,
            name=name,
        )
        return {"success": True}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        if error == "already_reacted":
            return {"success": True, "skipped": "already_reacted"}
        return {"success": False, "error": error}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _get_permalink(client, *, channel, message_ts):
    _assert_test_channel(channel)
    return client.chat_getPermalink(
        channel=channel,
        message_ts=message_ts,
    )["permalink"]


def seed_scenario_reactions(
    client,
    scenario,
    root_ts,
    *,
    state,
    state_path=STATE_FILE,
):
    results = []
    for name in scenario.reaction_names:
        result = _add_reaction(
            client,
            channel=TEST_CHANNEL,
            timestamp=root_ts,
            name=name,
        )
        results.append(result)
        if result["success"]:
            continue
        issue = {
            "channel": TEST_CHANNEL,
            "ts": root_ts,
            "name": name,
            "error": result["error"],
        }
        state.setdefault("reaction_errors", []).append(issue)
        _write_state(state, state_path)
        logger.error(
            "Could not seed :%s: on validation message %s: %s",
            name,
            root_ts,
            result["error"],
        )
    return results


def post(*, state_path=STATE_FILE):
    """Post all synthetic scenarios, recording each message immediately."""
    _assert_test_channel(TEST_CHANNEL)
    state_path = Path(state_path)
    if state_path.exists():
        raise RuntimeError(
            f"Validation state exists at {state_path}; run teardown first"
        )

    state = _new_state()
    _write_state(state, state_path)
    client = get_slack_client()
    for name, scenario in SCENARIOS.items():
        root_blocks, root_fallback, details = build_scenario(name, scenario)
        marked_root_blocks = _with_run_marker(
            root_blocks,
            state["run_id"],
            name,
        )
        root = _post_recorded(
            client,
            state,
            state_path=state_path,
            channel=TEST_CHANNEL,
            blocks=marked_root_blocks,
            text=f"[{state['run_id']}] {root_fallback}",
            unfurl_links=False,
            unfurl_media=False,
        )
        if details:
            details_blocks, details_fallback = details
            marked_details_blocks = _with_run_marker(
                details_blocks,
                state["run_id"],
                name,
                details=True,
            )
            _post_recorded(
                client,
                state,
                state_path=state_path,
                channel=TEST_CHANNEL,
                thread_ts=root["ts"],
                blocks=marked_details_blocks,
                text=f"[{state['run_id']}] {details_fallback}",
                reply_broadcast=False,
            )
        seed_scenario_reactions(
            client,
            scenario,
            root["ts"],
            state=state,
            state_path=state_path,
        )
        permalink = _get_permalink(
            client,
            channel=TEST_CHANNEL,
            message_ts=root["ts"],
        )
        print(f"{name}: {permalink}")
    return state


def _delete_record(client, record):
    _assert_test_channel(record["channel"])
    try:
        client.chat_delete(
            channel=record["channel"],
            ts=record["ts"],
        )
        return {"success": True}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        if error == "message_not_found":
            return {"success": True, "skipped": "already_absent"}
        return {"success": False, "error": error}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def teardown(*, state_path=STATE_FILE):
    """Incrementally remove recorded replies before their parent roots."""
    _assert_test_channel(TEST_CHANNEL)
    state_path = Path(state_path)
    if not state_path.exists():
        return {"success": True, "skipped": "no_state"}

    state = _load_state(state_path)
    records = state.get("records", [])
    if not records:
        state_path.unlink()
        return {"success": True}

    replies = [item for item in reversed(records) if item.get("thread_ts")]
    roots = [item for item in reversed(records) if not item.get("thread_ts")]
    client = get_slack_client()
    for record in replies + roots:
        result = _delete_record(client, record)
        if not result["success"]:
            _write_state(state, state_path)
            return {"success": False, "record": record, **result}
        state["records"].remove(record)
        if state["records"]:
            _write_state(state, state_path)
        else:
            state_path.unlink(missing_ok=True)

    return {"success": True}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"post", "teardown"}:
        print(
            "Usage: env/bin/python scripts/validate_announcement.py "
            "{post|teardown}",
            file=sys.stderr,
        )
        return 2

    app = create_app()
    with app.app_context():
        (post if args[0] == "post" else teardown)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
