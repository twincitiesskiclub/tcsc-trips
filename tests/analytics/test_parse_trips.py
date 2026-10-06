"""Hand-written Workflow posts with fake names and IDs."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.analytics.drafts import ArchivedMessage, TripSignup
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from app.analytics.parse_trips import edition_year, normalize_name, parse_signup, trip_sessions

TRIP = "C068ECRE0PQ"
HEADER = "Trip Signup Submitted. This does not mean that they have paid!"


@pytest.fixture
def cfg():
    return load_history_config()


def _post(body, username, when=datetime(2099, 11, 20, 12, 0)):
    ts = f"{when.replace(tzinfo=ZoneInfo('America/Chicago')).timestamp():.6f}"
    raw = {"ts": ts, "subtype": "bot_message", "username": username, "text": f"{HEADER}\n{body}"}
    return ArchivedMessage(TRIP, ts, raw)


def test_edition_year_and_name_normalizing():
    assert edition_year(date(2099, 6, 1)) == 2099
    assert edition_year(date(2099, 5, 31)) == 2098
    assert normalize_name("  Pat   EXAMPLE ") == "pat example"


def test_typed_name_line(cfg):
    signup = parse_signup(_post("Pat Example", "Cuyuna Trip Sign-Up"), cfg)
    assert (signup.series_slug, signup.edition_year, signup.person_name, signup.slack_uid) == (
        "cuyuna", 2099, "Pat Example", None)


def test_bare_mention(cfg):
    signup = parse_signup(_post("\n<@UFAKE0001>", "Birkie Sign-Up"), cfg)
    assert (signup.series_slug, signup.slack_uid, signup.person_name) == ("birkie", "UFAKE0001", None)


def test_first_last_form(cfg):
    body = ("\n*What's your first name?*\nPat \n*What's your last name?*\nExample\n"
            "*Dietary needs*\nNone")
    signup = parse_signup(_post(body, "Great Bear Chase Trip Sign-Up", datetime(2099, 1, 22)), cfg)
    assert (signup.series_slug, signup.edition_year, signup.person_name) == (
        "great-bear-chase", 2098, "Pat Example")


def test_typed_name_wins_over_mentions(cfg):
    body = ("\n*What's your name?*\nPat Example\n\n<@UFAKE0009>\n<#C02HXN45214|>\n<@UFAKE0008>\n"
            "Nov 21, 2099 12:40am UTC")
    signup = parse_signup(_post(body, "Sisu Trip Sign-Up"), cfg)
    assert (signup.series_slug, signup.person_name, signup.slack_uid) == ("sisu-ski-fest", "Pat Example", None)


def test_single_mention_kept_as_fallback(cfg):
    body = "\n*What's your name?*\nPat Example\n\n<@UFAKE0009>\n<#C02HXN45214|>\n<@UFAKE0009>"
    signup = parse_signup(_post(body, "Sisu Trip Sign-Up"), cfg)
    assert (signup.person_name, signup.slack_uid) == ("Pat Example", "UFAKE0009")


def test_pre_birkie_is_not_birkie_and_unknown_series_is_none(cfg):
    assert parse_signup(_post("Pat Example", "Pre-Birkie and North-end Classic Trip Sign-Up"), cfg).series_slug == "pre-birkie"
    assert parse_signup(_post("Pat Example", "Moon Base Trip Sign-Up"), cfg) is None
    join = ArchivedMessage(TRIP, "1.0", {"ts": "1.0", "subtype": "channel_join", "text": "joined"})
    assert parse_signup(join, cfg) is None


def test_trip_sessions_dedupe_and_date_correction():
    signups = [
        TripSignup("cuyuna", 2099, date(2099, 8, 7), None, "Pat Example", "C:1"),
        TripSignup("cuyuna", 2099, date(2099, 8, 9), None, "pat  example", "C:2"),     # duplicate
        TripSignup("cuyuna", 2099, date(2099, 8, 10), "UFAKE0002", None, "C:3"),
        TripSignup("cuyuna", 2098, date(2098, 8, 1), "UFAKE0002", None, "C:4"),        # other edition
    ]
    sessions, attendance = trip_sessions(signups, {"trip:cuyuna:2099": {"date": "2099-09-25",
                                                                         "title": "Cuyuna 2099"}}, [])
    by_key = {s.session_key: s for s in sessions}
    ours = by_key["trip:cuyuna:2099"]
    assert (ours.kind, ours.category, ours.date, ours.title, ours.rsvp_count, ours.flags) == (
        "trip", "trip", date(2099, 9, 25), "Cuyuna 2099", 2, [])
    other = by_key["trip:cuyuna:2098"]
    assert other.flags == ["missing_date"] and other.date == date(2098, 8, 1) and other.needs_review
    rows = [(a.session_key, a.slack_uid, a.person_name, a.role) for a in attendance]
    assert sorted(rows, key=str) == sorted([
        ("trip:cuyuna:2099", None, "pat example", "signup"),
        ("trip:cuyuna:2099", "UFAKE0002", None, "signup"),
        ("trip:cuyuna:2098", "UFAKE0002", None, "signup"),
    ], key=str)


def test_build_lineage_includes_trips_and_flags_unparsed(cfg):
    good = _post("Pat Example", "Cuyuna Trip Sign-Up")
    bad = _post("Pat Example", "Moon Base Trip Sign-Up", datetime(2099, 11, 21))
    result = build_lineage([good, bad], [], [], [], cfg)
    assert [s.session_key for s in result.sessions] == ["trip:cuyuna:2099"]
    assert result.possible_misses == [f"{TRIP}:{bad.ts}"]
    resolved = build_lineage([good, bad], [], [], [], cfg, {f"{TRIP}:{bad.ts}": {"skip": True}})
    assert resolved.possible_misses == []


def test_build_lineage_combines_app_and_slack_signups(cfg):
    good = _post("<@UFAKE0001>", "Cuyuna Trip Sign-Up")
    app_signups = [
        TripSignup("cuyuna", 2099, date(2099, 11, 22), "UFAKE0001", None, "trip_registration:1", 11),
        TripSignup("cuyuna", 2099, date(2099, 11, 23), "UFAKE0002", None, "trip_registration:2", 12),
    ]
    result = build_lineage([good], [], [], [], cfg, trip_signups=app_signups)
    assert len(result.sessions) == 1
    assert result.sessions[0].rsvp_count == 2
    assert result.sessions[0].date == date(2099, 11, 23)
    assert len(result.attendance) == 2


def test_trip_edition_skip():
    signup = TripSignup("cuyuna", 2099, date(2099, 8, 7), None, "Pat Example", "C:1")
    assert trip_sessions([signup], {"trip:cuyuna:2099": {"skip": True}}, []) == ([], [])


@pytest.mark.parametrize("source_key, expected", [("trip_registration:1", "app"), ("C:1", "post_text")])
def test_trip_attendance_source(source_key, expected):
    signup = TripSignup("cuyuna", 2099, date(2099, 8, 7), "UFAKE0001", None, source_key)
    _, attendance = trip_sessions([signup], {}, [])
    assert attendance[0].source == expected


@pytest.mark.parametrize("uid", [None, "UFAKE0001"])
def test_trip_sessions_dedupe_app_signups_and_keep_distinct_users(uid):
    signups = [
        TripSignup("cuyuna", 2099, date(2099, 8, 7), uid, None, "trip_registration:1", user_id=11),
        TripSignup("cuyuna", 2099, date(2099, 8, 8), uid, None, "trip_registration:2", user_id=11),
        TripSignup("cuyuna", 2099, date(2099, 8, 9), None, None, "trip_registration:3", user_id=12),
    ]
    sessions, attendance = trip_sessions(signups, {}, [])
    assert sessions[0].rsvp_count == 2
    assert [(row.user_id, row.slack_uid, row.source) for row in attendance] == [
        (11, uid, "app"), (12, None, "app")]


def test_unparsed_known_series_is_a_possible_miss(cfg):
    bad = _post("", "Cuyuna Trip Sign-Up")
    result = build_lineage([bad], [], [], [], cfg)
    assert result.sessions == []
    assert result.possible_misses == [f"{TRIP}:{bad.ts}"]
