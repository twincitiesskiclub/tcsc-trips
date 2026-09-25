"""Invented examples with expectations derived from the template parsing rules."""
from copy import deepcopy
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.analytics.drafts import ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.parse_template import (
    extract_template_sessions, is_weekly_preview, looks_like_template,
    parse_bop, parse_header, parse_people, parse_times, parse_title, parse_venue,
)
from tests.analytics.conftest import load_fixture

CASES = load_fixture("template_messages.json")
CENTRAL = ZoneInfo("America/Chicago")
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
        LocationRef(34, "Theodore Wirth", "Xerxes Field", 44.98, -93.31)]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


def message(text, posted="2099-07-16T08:00"):
    ts = f"{datetime.fromisoformat(posted).replace(tzinfo=CENTRAL).timestamp():.6f}"
    return ArchivedMessage("CFAKE0001", ts, {"ts": ts, "text": text}, archive_id=42)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden(case, cfg):
    raw = case["raw"]
    assert datetime.fromtimestamp(float(raw["ts"]), CENTRAL).replace(tzinfo=None) == (
        datetime.fromisoformat(case["posted_at_central"]))
    original = deepcopy(raw)
    msg = ArchivedMessage(case["channel_id"], raw["ts"], raw, archive_id=42)
    sessions = extract_template_sessions(msg, cfg, LOCS)
    exp = case["expected"]
    assert is_weekly_preview(raw["text"]) == exp.get("weekly_preview", False)
    assert len(sessions) == len(exp["sessions"])
    for got, want in zip(sessions, exp["sessions"]):
        assert got.group_key == f'{case["channel_id"]}:{raw["ts"]}'
        assert got.session_key == got.group_key + want["key_suffix"]
        assert got.date == date.fromisoformat(want["date"])
        assert got.start_time == (time.fromisoformat(want["start"]) if want.get("start") else None)
        assert got.rsvp_emoji == want["rsvp_emoji"]
        assert got.format == want["format"]
        assert got.slot == (want["key_suffix"][1:] if want["format"] == "split" else None)
        assert got.kind == want.get("kind", "practice")
        assert sorted(got.flags) == sorted(want.get("flags", []))
        assert (got.era, got.channel_id, got.source_ts, got.source_archive_id) == (
            "template", case["channel_id"], raw["ts"], 42)
        for key in ("title", "activities", "workout_types", "activity", "workout_type",
                    "lead_uids", "coach_uids", "venue_raw", "is_indoor", "location_id",
                    "location_name", "lat", "lon", "rsvp_emoji_set"):
            if key in want:
                assert getattr(got, key) == want[key], key
    assert raw == original


@pytest.mark.parametrize("header,posted,dates,flags", [
    ("_Tuesday, Jan 31_ • _TCSC_", "2023-01-31T08:00", [date(2023, 1, 31)], []),
    ("_Thursday, Jun 8th, 2023_", "2023-06-15T09:00", [date(2023, 6, 15)], ["date_mismatch"]),
    ("_Friday, Jan 31st, 2024_", "2025-01-30T12:00", [date(2025, 1, 31)], ["date_mismatch"]),
    ("_Thursday, Jul 17th, 2099_", "2099-07-16T08:00", [date(2099, 7, 16)], ["date_mismatch"]),
    ("Thursday, 10/26/2023 @ 6:00 PM", "2023-10-26T08:00", [date(2023, 10, 26)], []),
    ("Wednesday &amp; Friday, December 3rd &amp; 5th, 2025", "2025-12-03T08:00",
     [date(2025, 12, 3), date(2025, 12, 5)], []),
    ("Thursday, Jan 1", "2025-12-31T08:00", [date(2026, 1, 1)], []),
    ("Thursday, Jan 1, 2025", "2025-12-31T08:00", [date(2026, 1, 1)], ["date_mismatch"]),
    ("Friday, Feb 30, 2025", "2025-02-27T08:00", [date(2025, 2, 28)], ["date_mismatch"]),
    ("Wednesday, Jul 15, 2099", "2099-07-16T08:00", [date(2099, 7, 15)], []),
    ("Friday, Jul 24, 2099", "2099-07-16T08:00", [date(2099, 7, 24)], []),
    ("No date header", "2099-07-16T08:00", [], []),
])
def test_headers(header, posted, dates, flags):
    assert parse_header(header, datetime.fromisoformat(posted)) == (dates, flags)


@pytest.mark.parametrize("text,expected", [
    ("*Time:* 6:05 PM :six: & 7:20 PM :seven:", [time(18, 5), time(19, 20)]),
    ("Thursday, 10/26/2023 @ 6:00 & 7:00 PM", [time(18), time(19)]),
    ("6:00 & 7:00 & 8:00 AM", [time(6), time(7), time(8)]),
    ("1:15 9:30 10:45 18:05", [time(13, 15), time(21, 30), time(10, 45), time(18, 5)]),
    ("12:00 AM & 12:00 PM", [time(0), time(12)]),
    ("7:00 am and 6:00 pm", [time(7), time(18)]),
    ("Time: TBD", []),
])
def test_parse_times(text, expected):
    assert parse_times(text) == expected


def test_parse_bop_orders_and_labels():
    text = "*Bop that* :zap: *(for 6:00PM session) or* :white_check_mark: *(for 7:00PM session)*"
    assert parse_bop(text) == [("zap", "for 6:00PM session"), ("white_check_mark", "for 7:00PM session")]


@pytest.mark.parametrize("ending", ["so we'll know :other:", "if you'll come :other:", "\n:other:"])
def test_bop_limits_and_keeps_emoji_underscores(ending):
    assert parse_bop("*Bop that* :white_check_mark: " + ending) == [("white_check_mark", None)]
    assert parse_bop(":six: outside bop text") == []


@pytest.mark.parametrize("text", [
    ":date: • _Week of Oct 22, 2023_", "There are *2* events this week",
    "There are 12 events", "Weekly Practice Summary", "Practices this week",
    "_Additional details are available in the TCSC Team Calendar..._",
])
def test_weekly_preview_detection(text):
    assert is_weekly_preview(text)
    assert not is_weekly_preview("*Bop that* :white_check_mark:")


def test_template_detection():
    assert looks_like_template("Thursday, 10/26/2023 @ 6:00 & 7:00 PM")
    assert looks_like_template("_Thursday, July 16th, 2099_\nWorkout: Strength")
    assert not looks_like_template("Thursday, July 16th, 2099")
    assert not looks_like_template("Time: 6:00 PM")
    assert not looks_like_template("x" * 301 + " Thursday, Jul 16, 2099\nTime: 6:00 PM")


def test_people_and_field_prefixes():
    text = ("&gt;:people_holding_hands:  *Leads:* <@UFAKE0101> &amp; <@UFAKE0102>\n"
            "*Coach:* <@UFAKE0201>\n&gt; :whistle: *Coaches:* <@UFAKE0202>\n"
            "Details: ask Leads: <@UFAKE0999>\nLeads: <@UFAKE0103>\n")
    assert parse_people(text, "Leads") == ["UFAKE0101", "UFAKE0102", "UFAKE0103"]
    assert parse_people(text, "Coach:") == ["UFAKE0201"]
    assert parse_people(text, "Coaches") == ["UFAKE0202"]


def test_title_venue_and_workout_fallback():
    text = ("_Thursday, Jul 16, 2099_\n*Details @ ignored*\n"
            "*Run w/ Poles - Intervals* *@* *Theodore Wirth Trails*\n"
            "&gt; :pushpin: *Location:* Balance Fitness Studio")
    assert parse_title(text) == "Run w/ Poles - Intervals"
    assert parse_venue(text) == "Balance Fitness Studio"
    assert parse_title("Header\n\nWorkout: *Strength &amp; Circuit*\nCoach: <@UFAKE0201>") == "Strength & Circuit"
    assert parse_venue("Workout: Strength") is None
    assert parse_title("\n".join(["intro"] * 5 + ["Run @ Park"])) == ""


def test_exact_future_split(cfg):
    text = ("_Thursday, Jul 16th, 2099_ • _TCSC_\n"
            "*Strength Circuit @ Balance Fitness Studio*\n"
            "*Time:* 6:05 PM :six: & 7:20 PM :seven:\n"
            "*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*")
    sessions = extract_template_sessions(message(text), cfg, LOCS)
    assert [(s.slot, s.rsvp_emoji, s.start_time) for s in sessions] == [
        ("early", "six", time(18, 5)), ("late", "seven", time(19, 20))]
    for session in sessions:
        assert session.date == date(2099, 7, 16)
        assert session.activities == ["Strength"]
        assert session.workout_types == ["Circuit"]
        assert session.is_indoor is True
        assert session.flags == []


def test_exact_future_unknown(cfg):
    text = "_Thursday, Jul 16th, 2099_\n*Super Secret Surprise @ Nowhere*"
    session, = extract_template_sessions(message(text), cfg, LOCS)
    assert session.flags == ["unknown_venue", "unmatched_title"]
    assert session.rsvp_emoji == "white_check_mark"
    assert (session.format, session.start_time, session.activities) == ("single", None, [])


@pytest.mark.parametrize("bop", [
    "*Bop that* :late: *(7:20PM) or* :early: *(6:05PM)*",
    "*Bop that* :late: *(7:20PM) or* :early:",
])
def test_split_sorts_times_with_emoji_and_label_precedence(cfg, bop):
    msg = message("_Thursday, Jul 16, 2099_\n*Strength @ Balance Fitness Studio*\n"
                  "Time: 7:20 PM & 6:05 PM\n" + bop)
    sessions = extract_template_sessions(msg, cfg, LOCS)
    assert [(s.slot, s.rsvp_emoji, s.start_time) for s in sessions] == [
        ("early", "early", time(18, 5)), ("late", "late", time(19, 20))]


def test_label_times_override_time_line(cfg):
    msg = message("Thursday, Jul 16, 2099\nStrength @ Balance Fitness Studio\n"
                  "Time: 5:00 PM & 8:00 PM\nBop that :six: (6:05PM) or :seven: (7:20PM)")
    assert [s.start_time for s in extract_template_sessions(msg, cfg, LOCS)] == [time(18, 5), time(19, 20)]


def test_multi_day_time_line_fallback(cfg):
    msg = message("Wednesday & Friday, Dec 3 & 5, 2025\nRun @ Theodore Wirth Trails\n"
                  "Time: 6:30 PM & 7:00 AM\nBop that :white_check_mark: or :ballot_box_with_check:",
                  "2025-12-03T08:00")
    sessions = extract_template_sessions(msg, cfg, LOCS)
    assert [(s.date, s.start_time, s.format, s.flags) for s in sessions] == [
        (date(2025, 12, 3), time(18, 30), "single", ["multi_day"]),
        (date(2025, 12, 5), time(7), "single", ["multi_day"])]


def test_single_time_uses_time_line_then_header_only(cfg):
    msg = message("Thursday, Jul 16, 2099 @ 6:00 PM\nWorkout: Strength\n"
                  "Location: Balance Fitness Studio\nTime: 7:00 AM\n"
                  "Coach: <@UFAKE0201>\nCoaches: <@UFAKE0202>\nDetails: meet at 5:00 PM")
    session, = extract_template_sessions(msg, cfg, LOCS)
    assert session.start_time == time(7)
    assert session.coach_uids == ["UFAKE0201", "UFAKE0202"]
    session, = extract_template_sessions(message(msg.raw["text"].replace("Time: 7:00 AM\n", "")), cfg, LOCS)
    assert session.start_time == time(18)


def test_missing_location_row_and_config_only_location(cfg):
    text = "Thursday, Jul 16, 2099\nStrength @ Balance Fitness Studio"
    session, = extract_template_sessions(message(text), cfg, [])
    assert session.flags == ["unknown_location_row"]
    assert session.is_indoor is True
    session, = extract_template_sessions(message(text.replace("Balance Fitness Studio", "Beards Plaisance")), cfg, [])
    assert session.flags == []
    assert session.location_id is None
    assert (session.lat, session.lon) == (44.9215, -93.3100)


def test_single_ignores_body_and_bop_times(cfg):
    msg = message("Thursday, Jul 16, 2099\nStrength @ Balance Fitness Studio\n"
                  "Details: doors open at 5:00 PM\nBop that :zap: (6:00 PM)")
    session, = extract_template_sessions(msg, cfg, LOCS)
    assert session.start_time is None
    assert session.rsvp_emoji == "zap"


def test_raw_timestamp_supplies_post_date_and_envelope_supplies_identity(cfg):
    raw_msg = message("Thursday, Jul 16, 2099\nStrength @ Balance Fitness Studio")
    msg = ArchivedMessage(raw_msg.channel_id, "1.000000", raw_msg.raw)
    session, = extract_template_sessions(msg, cfg, LOCS)
    assert session.date == date(2099, 7, 16)
    assert session.source_ts == "1.000000"
    assert session.source_archive_id is None
    assert session.session_key == "CFAKE0001:1.000000:main"


def test_bop_controls_rsvp_despite_other_time_emoji(cfg):
    msg = message("Thursday, Jul 16, 2099\nStrength @ Balance Fitness Studio\n"
                  "Time: 6:05 PM :six: & 7:20 PM :seven:\nBop that :zap: or :white_check_mark:")
    sessions = extract_template_sessions(msg, cfg, LOCS)
    assert [(s.rsvp_emoji, s.start_time) for s in sessions] == [
        ("zap", time(18, 5))]
    assert sessions[0].rsvp_emoji_set == ["zap", "white_check_mark"]
    assert sessions[0].flags == ["emoji_ambiguous"]


def test_multi_day_without_second_weekday_keeps_distinct_dates_and_keys(cfg):
    header = "Tuesday, Dec 2nd & 4th, 2025"
    assert parse_header(header, datetime(2025, 12, 2, 8)) == (
        [date(2025, 12, 2), date(2025, 12, 4)], [])
    msg = message(header + "\n*Run @ Theodore Wirth Trails*\n"
                  "*Bop that* :white_check_mark: *(6:30 PM) or* :ballot_box_with_check: *(7:00 AM)*",
                  "2025-12-02T08:00")
    sessions = extract_template_sessions(msg, cfg, LOCS)
    assert [s.date for s in sessions] == [date(2025, 12, 2), date(2025, 12, 4)]
    assert [s.session_key for s in sessions] == [
        f"{msg.channel_id}:{msg.ts}:2025-12-02", f"{msg.channel_id}:{msg.ts}:2025-12-04"]
    assert [s.flags for s in sessions] == [["multi_day"], ["multi_day"]]


def test_lowercase_preview_phrases_in_body_do_not_drop_practice(cfg):
    msg = message("Thursday, Jul 16, 2099\n*Strength @ Balance Fitness Studio*\n"
                  "*Time:* 6:05 PM\nThis is the last week of the season; "
                  "practices this week are fun.\n*Bop that* :white_check_mark:")
    assert not is_weekly_preview(msg.raw["text"])
    session, = extract_template_sessions(msg, cfg, LOCS)
    assert (session.date, session.start_time, session.title) == (
        date(2099, 7, 16), time(18, 5), "Strength")
    assert session.flags == []


@pytest.mark.parametrize("header,bop", [
    ("Thursday, Jul 16, 2099", ":six: (6:05 PM) or :seven:"),
    ("Thursday & Friday, Jul 16 & 17, 2099", ":six: (Thursday) or :seven: (Friday)"),
])
@pytest.mark.parametrize("time_line,expected", [
    ("Time: 6:05 PM & 7:20 PM", [time(18, 5), time(19, 20)]),
    ("", None),
])
def test_split_and_multiday_fallback_ignores_unrelated_times(cfg, header, bop, time_line, expected):
    text = f"{header}\nEasy Run @ Theodore Wirth Trails\nMeet for a chat at 5:00 PM\n{time_line}\nBop that {bop}"
    sessions = extract_template_sessions(message(text), cfg, LOCS)
    if expected is None:
        expected = [time(18, 5), None] if "&" not in header else [None, None]
    assert [s.start_time for s in sessions] == expected
