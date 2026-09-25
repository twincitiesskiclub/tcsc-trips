from copy import deepcopy
from datetime import datetime, time

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.parse_app import extract_app_sessions, parse_rsvp_mapping

CH = "C042G463AQ1"
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
        LocationRef(35, "Hyland", "Visitor Center", 44.82, -93.37)]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


def P(id, dt, ts, emoji=None, **kw):
    base = dict(id=id, date=dt, status="scheduled", is_draft=False, slack_channel_id=CH,
                slack_message_ts=ts, slack_session_emoji=emoji,
                location_name="Balance Fitness Studio", location_spot=None,
                activities=("Strength",), types=("Circuit",))
    base.update(kw)
    return AppPractice(**base)


def test_split_lift_with_saved_emoji(cfg):
    ps = [P(1, datetime(2099, 5, 21, 18, 5), "4082.1", "six"),
          P(2, datetime(2099, 5, 21, 19, 20), "4082.1", "seven")]
    out = extract_app_sessions(ps, {(CH, "4082.1"): ArchivedMessage(CH, "4082.1", {"ts": "4082.1", "text": ""})}, cfg, LOCS)
    assert [(s.slot, s.rsvp_emoji, s.format, s.session_key) for s in out] == [
        ("early", "six", "split", "practice:1"), ("late", "seven", "split", "practice:2")]
    assert out[0].is_indoor and out[0].activity == "Strength"


def test_wed_fri_group_reads_mapping_from_post(cfg):
    text = "RSVP: :white_check_mark: Wed (6:30 PM) | :ballot_box_with_check: Fri (7:00 AM)"
    ps = [P(3, datetime(2099, 1, 7, 18, 30), "4083.1"), P(4, datetime(2099, 1, 9, 7, 0), "4083.1")]
    out = extract_app_sessions(ps, {(CH, "4083.1"): ArchivedMessage(CH, "4083.1", {"ts": "4083.1", "text": text})}, cfg, LOCS)
    assert [(s.rsvp_emoji, s.format, s.start_time) for s in out] == [
        ("white_check_mark", "single", time(18, 30)), ("ballot_box_with_check", "single", time(7, 0))]


def test_drafts_skipped_cancelled_kept_missing_post_flagged(cfg):
    ps = [P(5, datetime(2099, 2, 3, 18, 15), "4084.1", is_draft=True),
          P(6, datetime(2099, 2, 5, 18, 15), "4085.1", status="cancelled")]
    out = extract_app_sessions(ps, {}, cfg, LOCS)
    assert [s.practice_id for s in out] == [6]
    assert out[0].status == "cancelled" and "post_missing" in out[0].flags


def test_parse_rsvp_mapping():
    assert parse_rsvp_mapping("RSVP: :white_check_mark: Wed (6:30 PM) | :ballot_box_with_check: Fri (7:00 AM)") == {
        "white_check_mark": "Wed (6:30 PM)", "ballot_box_with_check": "Fri (7:00 AM)"}


@pytest.mark.parametrize("text,expected", [
    ("*RSVP:* :ballot_box_with_check: Friday | :white_check_mark: Wednesday",
     {"ballot_box_with_check": "Friday", "white_check_mark": "Wednesday"}),
    ("Lift: :seven: 7:20 | :six: 6:05", {"seven": "7:20", "six": "6:05"}),
    (":six: *6:05*\n:seven: *7:20*", {"six": "6:05", "seven": "7:20"}),
    ("Plans: :bike: 6:00 PM\nNo RSVP mapping", {}),
    ("RSVP: :six: TBD | :seven: TBD", {}),
    ("", {}),
])
def test_mapping_shapes(text, expected):
    assert parse_rsvp_mapping(text) == expected


@pytest.mark.parametrize("in_blocks", [False, True])
def test_lift_mapping_matches_times_not_order_or_default(cfg, in_blocks):
    # Deliberately reverse the usual emoji meaning to prove the post wins.
    text = ":six: 7:20 | :seven: 6:05"
    raw = {"text": "TCSC Lift - Thursday & Thursday" if in_blocks else text}
    if in_blocks:
        raw["blocks"] = [{"type": "section", "fields": [
            {"type": "mrkdwn", "text": text}]}]
    ps = [P(2, datetime(2099, 5, 21, 19, 20), "4082.1"),
          P(1, datetime(2099, 5, 21, 18, 5), "4082.1")]
    out = extract_app_sessions(ps, {(CH, "4082.1"): ArchivedMessage(CH, "4082.1", raw)}, cfg, LOCS)
    assert [(s.practice_id, s.slot, s.rsvp_emoji) for s in out] == [
        (1, "early", "seven"), (2, "late", "six")]


def test_weekday_only_mapping_in_nested_blocks(cfg):
    ps = [P(2, datetime(2099, 1, 9, 18, 30), "4083.1"),
          P(1, datetime(2099, 1, 7, 18, 30), "4083.1")]
    raw = {"text": "Practice on Tuesday, January 06", "blocks": [{
        "elements": [{"text": {"type": "mrkdwn", "text":
            "RSVP: :ballot_box_with_check: Fri | :white_check_mark: Wed"}}]}]}
    out = extract_app_sessions(ps, {(CH, "4083.1"): ArchivedMessage(CH, "4083.1", raw)}, cfg, LOCS)
    assert [(s.rsvp_emoji, s.format, s.slot) for s in out] == [
        ("white_check_mark", "single", None), ("ballot_box_with_check", "single", None)]


@pytest.mark.parametrize("day,activities,expected", [
    (21, ("Strength",), ["six", "seven"]),
    (22, ("Strength",), [None, None]),
    (21, ("Run",), [None, None]),
])
def test_split_fallback_only_for_thursday_strength(cfg, day, activities, expected):
    ps = [P(1, datetime(2099, 5, day, 18, 5), "4082.1", activities=activities),
          P(2, datetime(2099, 5, day, 19, 20), "4082.1", activities=activities)]
    out = extract_app_sessions(ps, {}, cfg, LOCS)
    assert [s.rsvp_emoji for s in out] == expected
    assert [("emoji_unknown" in s.flags) for s in out] == [e is None for e in expected]


def test_single_defaults_saved_emoji_and_skip_unposted(cfg):
    ps = [P(1, datetime(2099, 1, 7, 18, 30), "4083.1"),
          P(2, datetime(2099, 1, 9, 7), "4084.1", "custom"),
          P(3, datetime(2099, 1, 9, 7), None),
          P(4, datetime(2099, 1, 9, 7), "")]
    out = extract_app_sessions(ps, {}, cfg, LOCS)
    assert [(s.session_key, s.rsvp_emoji, s.format, s.slot) for s in out] == [
        ("practice:1", "white_check_mark", "single", None),
        ("practice:2", "custom", "single", None)]


def test_saved_emoji_takes_precedence_over_post(cfg):
    ps = [P(1, datetime(2099, 5, 21, 18, 5), "4082.1", "custom"),
          P(2, datetime(2099, 5, 21, 19, 20), "4082.1")]
    msg = ArchivedMessage(CH, "4082.1", {"text": ":six: 6:05 | :seven: 7:20"})
    assert [s.rsvp_emoji for s in extract_app_sessions(ps, {(CH, msg.ts): msg}, cfg, LOCS)] == [
        "custom", "seven"]


def test_multiday_unknown_mapping_is_flagged(cfg):
    ps = [P(1, datetime(2099, 1, 7, 18, 30), "4083.1"),
          P(2, datetime(2099, 1, 9, 7), "4083.1")]
    out = extract_app_sessions(ps, {}, cfg, LOCS)
    assert all(s.rsvp_emoji is None and "emoji_unknown" in s.flags for s in out)


def test_group_identity_includes_channel(cfg):
    ps = [P(1, datetime(2099, 1, 7, 18, 30), "4083.1"),
          P(2, datetime(2099, 1, 7, 19, 30), "4083.1", slack_channel_id="CFAKE0002")]
    msg = ArchivedMessage(CH, "4083.1", {"text": ""}, archive_id=99)
    out = extract_app_sessions(ps, {(CH, msg.ts): msg}, cfg, LOCS)
    assert [s.group_key for s in out] == [f"{CH}:4083.1", "CFAKE0002:4083.1"]
    assert [s.source_archive_id for s in out] == [99, None]
    assert [s.flags for s in out] == [[], ["post_missing"]]
    assert all(s.format == "single" for s in out)


@pytest.mark.parametrize("name,spot,locations,location_id,resolved,indoor,flags", [
    ("Hyland", "Visitor Center", LOCS, 35, "Hyland", False, []),
    ("Hopkins Highschool", "Royals Athletic Center",
     [LocationRef(9, "Hopkins Highschool", "Royals Athletic Center", None, None)],
     9, "Hopkins Highschool", True, []),
    ("Balance Fitness", None, LOCS, 38, "Balance Fitness Studio", True, []),
    ("Balance Fitness", None, [], None, "Balance Fitness Studio", True, ["unknown_location_row"]),
    ("Beards Plaisance", None, [], None, "Beards Plaisance", False, []),
    ("Imaginary Park", None, LOCS, None, None, False, ["unknown_venue"]),
    (None, None, LOCS, None, None, False, ["unknown_venue"]),
])
def test_venue_resolution(cfg, name, spot, locations, location_id, resolved, indoor, flags):
    p = P(1, datetime(2099, 1, 7, 18, 30), "4083.1", location_name=name, location_spot=spot)
    msg = ArchivedMessage(CH, "4083.1", {"text": ""})
    s, = extract_app_sessions([p], {(CH, msg.ts): msg}, cfg, locations)
    assert (s.location_id, s.location_name, s.is_indoor, s.flags) == (location_id, resolved, indoor, flags)
    if name in (None, "Imaginary Park", "Hopkins Highschool"):
        assert (s.lat, s.lon) == (cfg.default_lat, cfg.default_lon)
    elif location_id == 35:
        assert (s.lat, s.lon) == (44.82, -93.37)


def test_classification_provenance_and_purity(cfg):
    ps = [P(1, datetime(2099, 1, 7, 18, 30), "4083.1",
            activities=("Run", "Bike", "Kickoff"), types=("Endurance", "Technique"),
            lead_uids=("UFAKE0001",), coach_uids=("UFAKE0002",), plan_emoji=("bike",))]
    msg = ArchivedMessage(CH, "4083.1", {"text": ""}, archive_id=99)
    messages = {(CH, msg.ts): msg}
    before = deepcopy((ps, messages, cfg, LOCS))
    s, = extract_app_sessions(ps, messages, cfg, LOCS)
    assert (s.era, s.date, s.start_time, s.channel_id, s.source_ts, s.source_archive_id) == (
        "app", ps[0].date.date(), time(18, 30), CH, msg.ts, 99)
    assert (s.title, s.kind, s.activity, s.workout_type, s.status) == (
        "Run, Bike, Kickoff - Endurance, Technique", "event", "Multisport", "Technique", "held")
    assert (s.activities, s.workout_types, s.lead_uids, s.coach_uids, s.plan_emoji) == (
        ["Run", "Bike", "Kickoff"], ["Endurance", "Technique"], ["UFAKE0001"], ["UFAKE0002"], ["bike"])
    s.activities.append("Strength")
    s.flags.append("test")
    assert (ps, messages, cfg, LOCS) == before


def test_empty_classification_has_practice_title(cfg):
    p = P(1, datetime(2099, 1, 7, 18, 30), "4083.1", activities=(), types=())
    s, = extract_app_sessions([p], {}, cfg, LOCS)
    assert (s.title, s.activity, s.workout_type, s.kind) == ("Practice", "Other", "Other", "practice")
