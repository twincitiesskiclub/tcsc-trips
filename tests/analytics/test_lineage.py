from datetime import date, datetime, time
from dataclasses import replace

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef, SessionDraft
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage, session_category

CH = "C042G463AQ1"
BOT, ZAP = "U06FYPUNQCU", "U04C46UJXAM"
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28)]
SPLIT_TEXT = ("_Thursday, Jul 16th, 2099_ • _TCSC_\n*Strength Circuit @ Balance Fitness Studio*\n"
              "*Time:* 6:05 PM :six: & 7:20 PM :seven:\n*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*")


@pytest.fixture
def cfg():
    return load_history_config()


def _ts(dt):  # naive Central -> Slack ts string; tests only need ordering and the date
    from zoneinfo import ZoneInfo
    return f"{dt.replace(tzinfo=ZoneInfo('America/Chicago')).timestamp():.6f}"


def _post(text, reactions, when=datetime(2099, 7, 16, 8, 0), replies=()):
    ts = _ts(when)
    raw = {"ts": ts, "text": text, "reactions": reactions}
    return ArchivedMessage(CH, ts, raw, replies=tuple(replies))


def R(name, *users):
    return {"name": name, "count": len(users), "users": list(users)}


def test_create_session_from_no_header_post(cfg):
    from copy import deepcopy

    msg = replace(_post("\n  *Official RSVP for _strength_ tomorrow at 7 am &amp; a stretch*  \nDetails below",
                        [R("white_check_mark", BOT, "UFAKE0001", "UFAKE0002", "UFAKE0003", "UFAKE0004")]),
                  archive_id=42)
    key = f"{CH}:{msg.ts}"
    corrections = {key: {"create": True, "date": "2099-07-17", "start_time": "07:00",
                         "location": "Balance Fitness Studio", "activities": ["Strength"]}}
    before = deepcopy((msg, corrections))
    assert build_lineage([msg], [], LOCS, [], cfg).possible_misses == [key]
    result = build_lineage([msg], [], LOCS, [], cfg, corrections)
    session, = result.sessions
    assert (session.session_key, session.group_key, session.era, session.format, session.slot) == (
        key + ":main", key, "template", "single", None)
    assert (session.date, session.start_time, session.rsvp_count) == (date(2099, 7, 17), time(7), 4)
    assert session.title == "Official RSVP for strength tomorrow at 7 am & a stretch"
    assert (session.venue_raw, session.location_name, session.location_id, session.is_indoor) == (
        "Balance Fitness Studio", "Balance Fitness Studio", 38, True)
    assert (session.lat, session.lon) == (44.95, -93.28)
    assert (session.activities, session.activity, session.workout_types, session.workout_type) == (
        ["Strength"], "Strength", ["Circuit"], "Circuit")
    assert (session.channel_id, session.source_ts, session.source_archive_id) == (CH, msg.ts, 42)
    assert (session.kind, session.status, session.flags, session.needs_review) == ("practice", "held", [], False)
    assert session.rsvp_emoji_set == ["white_check_mark"]
    assert result.possible_misses == []
    assert {row.slack_uid for row in result.attendance} == {f"UFAKE000{i}" for i in range(1, 5)}
    assert all(row.role == "rsvp" and row.source == "reaction" for row in result.attendance)
    assert build_lineage([msg], [], LOCS, [], cfg, corrections) == result
    assert (msg, corrections) == before


@pytest.mark.parametrize("emojis,expected", [(["zap", "six"], 2), ([], 0)])
def test_create_honors_overrides_and_reaction_roles(cfg, emojis, expected):
    msg = _post("Strength tomorrow", [R("white_check_mark", "UFAKE0009"),
        R("zap::skin-tone-3", BOT, "UFAKE0001"), R("six", "UFAKE0001", "UFAKE0002"),
        R("coachface", BOT, "UFAKE0003"), R("book::skin-tone-2", "UFAKE0004")])
    cfg = replace(cfg, coach_emoji=frozenset({"coachface"}))
    corrections = {f"{CH}:{msg.ts}": {"create": True, "date": "2099-07-17",
        "activities": ["Run", "Bike"], "types": ["Intervals"], "kind": "event",
        "status": "cancelled", "rsvp_emoji": emojis, "plan_emoji": ["book"]}}
    result = build_lineage([msg], [], LOCS, [], cfg, corrections)
    session, = result.sessions
    assert (session.activities, session.activity, session.workout_types, session.workout_type) == (
        ["Run", "Bike"], "Multisport", ["Intervals"], "Intervals")
    assert (session.kind, session.status, session.start_time, session.rsvp_count) == (
        "event", "cancelled", None, expected)
    assert session.rsvp_emoji_set == emojis
    assert {(row.slack_uid, row.role) for row in result.attendance if row.role != "rsvp"} == {
        ("UFAKE0003", "coach"), ("UFAKE0004", "plan")}


@pytest.mark.parametrize("title,activities,types,kind", [
    ("Strength tomorrow", ["Strength"], ["Circuit"], "practice"),
    ("Season kickoff potluck", ["Kickoff"], ["Kickoff"], "event"),
    ("x" * 140, [], [], "practice"),
])
def test_create_defaults_from_title(cfg, title, activities, types, kind):
    msg = _post("\n  " + title + "\nIgnored second line", [])
    result = build_lineage([msg], [], LOCS, [], cfg,
                           {f"{CH}:{msg.ts}": {"create": True, "date": "2099-07-17"}})
    session, = result.sessions
    assert session.title == title[:120]
    assert (session.activities, session.workout_types, session.kind) == (activities, types, kind)
    assert (session.start_time, session.location_id, session.status) == (None, None, "held")
    assert (session.lat, session.lon) == (cfg.default_lat, cfg.default_lon)
    assert session.flags == [] and not session.needs_review


@pytest.mark.parametrize("app_era", [False, True])
def test_create_does_not_duplicate_existing_sessions(cfg, app_era):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE0001")])
    practices = [AppPractice(9901, datetime(2099, 7, 16, 18, 5), "scheduled", False,
        CH, msg.ts, "six", "Balance Fitness Studio", None)] if app_era else []
    key = f"{CH}:{msg.ts}"
    fields = {"date": "2099-07-17", "activities": ["Run"]}
    expected = build_lineage([msg], practices, LOCS, [], cfg, {key: fields})
    result = build_lineage([msg], practices, LOCS, [], cfg, {key: {**fields, "create": True}})
    assert result == expected
    assert len(result.sessions) == (1 if app_era else 2)
    assert all(s.date == date(2099, 7, 17) and s.activity == "Run" for s in result.sessions)


@pytest.mark.parametrize("case", ["missing", "deleted", "reply", "off_channel", "false"])
def test_create_requires_eligible_archived_post(cfg, case):
    msg = _post("Official RSVP for strength tomorrow at 7 am", [R("white_check_mark", "UFAKE0001")])
    if case == "deleted":
        msg = replace(msg, deleted=True)
    elif case == "reply":
        msg = replace(msg, raw={**msg.raw, "thread_ts": "1.000000"})
    elif case == "off_channel":
        msg = replace(msg, channel_id="CFAKEOTHER")
    corrections = {f"{msg.channel_id}:{msg.ts}": {"create": case != "false", "date": "2099-07-17"}}
    result = build_lineage([] if case == "missing" else [msg], [], LOCS, [], cfg, corrections)
    assert result.sessions == [] and result.attendance == []


def test_excluded_accounts_never_attend(cfg):
    msg = _post(SPLIT_TEXT, [R("six", BOT, "UFAKE1", ZAP), R("seven", BOT, "UFAKE2")])
    res = build_lineage([msg], [], LOCS, [], cfg)
    uids = {a.slack_uid for a in res.attendance}
    assert BOT not in uids and ZAP not in uids
    assert [s.rsvp_count for s in res.sessions] == [1, 1]


def test_merge_needs_same_day_reply_and_correction_wins(cfg):
    same_day = {"ts": _ts(datetime(2099, 7, 16, 15, 0)), "text": "We're merging to one session at 6:30 tonight!"}
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1", "UFAKE3"), R("seven", "UFAKE2")], replies=[same_day])
    res = build_lineage([msg], [], LOCS, [], cfg)
    assert len(res.sessions) == 1
    s = res.sessions[0]
    assert (s.format, s.rsvp_count, s.start_time.hour, s.start_time.minute) == ("merged", 3, 18, 30)
    assert "merge_detected" in s.flags
    slots = sorted((a.slack_uid, a.slot) for a in res.attendance if a.role == "rsvp")
    assert slots == [("UFAKE1", "early"), ("UFAKE2", "late"), ("UFAKE3", "early")]

    next_day = {"ts": _ts(datetime(2099, 7, 17, 9, 0)), "text": "merging next week?"}
    res = build_lineage([replace(msg, replies=(next_day,))], [], LOCS, [], cfg)
    assert [s.format for s in res.sessions] == ["split", "split"]

    res = build_lineage([msg], [], LOCS, [], cfg, corrections={f"{CH}:{msg.ts}": {"merged": False}})
    assert [s.format for s in res.sessions] == ["split", "split"]


def test_coach_plan_and_lead_roles(cfg):
    text = SPLIT_TEXT + "\n*Leads:* <@UFAKE9>"
    msg = _post(text, [R("six", "UFAKE1"), R("coachface", "UFAKE7")])
    res = build_lineage([msg], [], LOCS, [], replace(cfg, coach_emoji=frozenset({"coachface"})))
    roles = {(a.slack_uid, a.role) for a in res.attendance}
    assert ("UFAKE7", "coach") in roles and ("UFAKE9", "lead") in roles
    assert ("UFAKE7", "rsvp") not in roles


def test_button_rsvps_union_without_double_count(cfg):
    ts = "4090000000.000100"
    p = AppPractice(id=900, date=datetime(2099, 1, 6, 18, 15), status="scheduled", is_draft=False,
                    slack_channel_id=CH, slack_message_ts=ts, slack_session_emoji=None,
                    location_name="Balance Fitness Studio", location_spot=None,
                    activities=("Strength",), types=("Circuit",),
                    button_rsvp_uids=("UFAKE1", "UFAKE5"))
    msg = ArchivedMessage(CH, ts, {"ts": ts, "text": "Practice on Tuesday",
                                   "reactions": [R("white_check_mark", "UFAKE1", BOT)]})
    res = build_lineage([msg], [p], LOCS, [], cfg)
    assert res.sessions[0].rsvp_count == 2
    sources = sorted((a.slack_uid, a.source) for a in res.attendance if a.role == "rsvp")
    assert sources == [("UFAKE1", "reaction"), ("UFAKE5", "button")]


def test_rsvp_from_other_message_and_skip(cfg):
    main = _post(SPLIT_TEXT, [R("six", "UFAKE1")])
    other_ts = _ts(datetime(2099, 7, 15, 20, 0))
    other = ArchivedMessage(CH, other_ts, {"ts": other_ts, "text": "official RSVP, add a check",
                                           "reactions": [R("six", "UFAKE4")]})
    corr = {f"{CH}:{main.ts}:early": {"rsvp_from": [f"{CH}:{other_ts}"]}}
    res = build_lineage([main, other], [], LOCS, [], cfg, corrections=corr)
    early = [s for s in res.sessions if s.slot == "early"][0]
    assert early.rsvp_count == 2
    corr[f"{CH}:{main.ts}"] = {"skip": True}
    assert build_lineage([main, other], [], LOCS, [], cfg, corrections=corr).sessions == []


def test_deleted_messages_and_weekly_previews_produce_nothing(cfg):
    gone = replace(_post(SPLIT_TEXT, [R("six", "UFAKE1")]), deleted=True)
    preview = _post(":date: • _Week of Jul 13, 2099_", [R("white_check_mark", "UFAKE1")])
    assert build_lineage([gone, preview], [], LOCS, [], cfg).sessions == []


def test_needs_review_and_possible_misses(cfg):
    odd = _post("_Thursday, Jul 16th, 2099_\n*Super Secret Surprise @ Nowhere*",
                [R("white_check_mark", "UFAKE1")])
    stray_ts = _ts(datetime(2099, 7, 10, 9))
    stray = ArchivedMessage(CH, stray_ts, {"ts": stray_ts, "text": "please check this message",
                                          "reactions": [R("white_check_mark", *[f"UFAKE{i}" for i in range(6)])]})
    res = build_lineage([odd, stray], [], LOCS, [], cfg)
    assert res.sessions[0].needs_review is True
    assert f"{CH}:{stray_ts}" in res.possible_misses
    ok = {res.sessions[0].session_key: {"ok": True}}
    assert build_lineage([odd], [], LOCS, [], cfg, corrections=ok).sessions[0].needs_review is False


def test_corrections_override_fields_and_attendance(cfg):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1"), R("zap::skin-tone-3", "UFAKE2"),
                             R("book::skin-tone-2", "UFAKE3")])
    post_key = f"{CH}:{msg.ts}"
    corrections = {
        post_key: {"kind": "event", "date": "2099-07-17", "start_time": "17:45",
                   "status": "cancelled", "location": "Balance Fitness Studio",
                   "activities": ["Run"], "types": ["Endurance"], "plan_emoji": ["book"],
                   "add": [{"slack_uid": "UFAKE4", "role": "lead"}]},
        post_key + ":early": {"kind": "practice", "rsvp_emoji": ["zap"],
                              "add": [{"slack_uid": "UFAKE5", "role": "rsvp"},
                                      {"slack_uid": BOT, "role": "rsvp"}],
                              "remove": [{"slack_uid": "UFAKE2", "role": "rsvp"}]},
    }
    from app.analytics.drafts import SeasonRef
    seasons = [SeasonRef("Test season", date(2099, 7, 1), date(2099, 8, 1))]
    res = build_lineage([msg], [], LOCS, seasons, cfg, corrections)
    early = next(s for s in res.sessions if s.slot == "early")
    assert (early.date, early.start_time.isoformat(), early.kind, early.status) == (
        date(2099, 7, 17), "17:45:00", "practice", "cancelled")
    assert (early.activity, early.workout_type, early.location_id) == ("Run", "Endurance", 38)
    assert (early.day_of_week, early.season_label, early.needs_review) == ("Friday", "Test season", False)
    rows = [a for a in res.attendance if a.session_key == early.session_key]
    assert {(a.slack_uid, a.role, a.source) for a in rows} == {
        ("UFAKE3", "plan", "reaction"), ("UFAKE4", "lead", "correction"),
        ("UFAKE5", "rsvp", "correction")}
    assert early.rsvp_count == 1


def test_cancel_language_uses_central_day_without_changing_status(cfg):
    replies = [{"ts": _ts(datetime(2099, 7, 16, 23, 30)), "text": "Consider cancelling?"}]
    msg = _post(SPLIT_TEXT, [], replies=replies)
    res = build_lineage([msg], [], LOCS, [], cfg)
    assert all("cancel_language" in s.flags and s.status == "held" for s in res.sessions)
    later = {"ts": _ts(datetime(2099, 7, 17, 0, 1)), "text": "cancelled"}
    res = build_lineage([replace(msg, replies=(later,))], [], LOCS, [], cfg)
    assert all("cancel_language" not in s.flags for s in res.sessions)


def test_manual_merge_and_merged_key_correction(cfg):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1"), R("seven", "UFAKE1", "UFAKE2")])
    key = f"{CH}:{msg.ts}:merged"
    res = build_lineage([msg], [], LOCS, [], cfg, {key: {"merged": True, "start_time": "18:40"}})
    assert len(res.sessions) == 1
    session = res.sessions[0]
    assert (session.session_key, session.format, session.slot, session.rsvp_emoji) == (key, "merged", None, None)
    assert (session.rsvp_count, session.start_time.isoformat(), session.needs_review) == (2, "18:40:00", False)
    assert "merge_detected" not in session.flags


def test_attendance_dedupes_across_sources_and_preserves_emoji(cfg):
    msg = _post(SPLIT_TEXT, [R("six::skin-tone-2", "UFAKE1"), R("six", "UFAKE1")])
    key = f"{CH}:{msg.ts}"
    res = build_lineage([msg], [], LOCS, [], cfg, {key: {"rsvp_from": [key, key]}})
    rows = [a for a in res.attendance if a.role == "rsvp"]
    assert len(rows) == 2
    assert {a.emoji for a in rows} == {"six", "six::skin-tone-2"}
    assert [s.rsvp_count for s in res.sessions] == [1, 0]


def test_thread_broadcast_does_not_create_a_session_but_can_merge(cfg):
    msg = _post(SPLIT_TEXT, [])
    ts = _ts(datetime(2099, 7, 16, 23, 30))
    reply = ArchivedMessage(CH, ts, {"ts": ts, "thread_ts": msg.ts,
                                    "text": SPLIT_TEXT + "\ncombining tonight at 6:30"})
    res = build_lineage([msg, reply], [], LOCS, [], cfg)
    assert len(res.sessions) == 1 and res.sessions[0].format == "merged"


def test_only_eligible_top_level_messages_are_possible_misses(cfg):
    reactions = [R("white_check_mark::skin-tone-3", *[f"UFAKE{i}" for i in range(5)])]
    msg = _post("Read this", reactions)
    off_channel = replace(msg, channel_id="CFAKEOTHER")
    reply = replace(msg, ts="4090000000.000200", raw={**msg.raw, "thread_ts": "parent"})
    unrelated = replace(msg, ts="4090000000.000300", raw={**msg.raw, "reactions": [R("heart", *range(6))]})
    res = build_lineage([msg, off_channel, reply, unrelated], [], LOCS, [], cfg)
    assert res.possible_misses == [f"{CH}:{msg.ts}"]


def test_possible_misses_include_event_rsvp_wording_and_non_applause_reactions(cfg):
    wording = replace(_post("Bop the :pickle:", []), channel_id="C02HXN45214")
    reactions = replace(_post("Cider tasting Saturday", [R("apple", *[
        f"UFAKE{i:04d}" for i in range(5)])]), channel_id="C0B2VN1LU11")
    result = build_lineage([reactions, wording], [], LOCS, [], cfg)
    assert result.sessions == []
    assert result.possible_misses == sorted([
        f"{wording.channel_id}:{wording.ts}", f"{reactions.channel_id}:{reactions.ts}"])


def test_app_merge_keeps_both_slots_buttons_and_plan_choices(cfg):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1"), R("seven", "UFAKE2"),
                             R("book", "UFAKE3"), R("bike", "UFAKE4")], replies=[{
        "ts": _ts(datetime(2099, 7, 16, 15)), "text": "One session at 6:30 tonight"}])
    early = AppPractice(901, datetime(2099, 7, 16, 18, 5), "scheduled", False,
                        CH, msg.ts, "six", "Balance Fitness Studio", None,
                        activities=("Strength",), button_rsvp_uids=("UFAKE1", "UFAKE5"),
                        coach_uids=("UFAKE7",), plan_emoji=("book",))
    late = replace(early, id=902, date=datetime(2099, 7, 16, 19, 20), slack_session_emoji="seven",
                   button_rsvp_uids=("UFAKE2", "UFAKE6"), lead_uids=("UFAKE8",),
                   plan_emoji=("bike",))
    corrections = {"practice:901": {"rsvp_emoji": ["six"], "plan_emoji": ["book"]}}
    res = build_lineage([msg], [late, early], LOCS, [], cfg, corrections)
    assert len(res.sessions) == 1
    session = res.sessions[0]
    assert (session.session_key, session.rsvp_count, session.start_time.isoformat()) == (
        "practice:901", 4, "18:30:00")
    assert session.rsvp_emoji is None
    assert {(a.slack_uid, a.slot) for a in res.attendance if a.source == "reaction" and a.role == "rsvp"} == {
        ("UFAKE1", "early"), ("UFAKE2", "late")}
    assert {a.slack_uid for a in res.attendance if a.role == "plan"} == {"UFAKE3", "UFAKE4"}
    assert {(a.slack_uid, a.role) for a in res.attendance if a.source == "app"} == {
        ("UFAKE7", "coach"), ("UFAKE8", "lead")}


def test_review_acknowledgement_is_for_resulting_session_or_post(cfg):
    reply = {"ts": _ts(datetime(2099, 7, 16, 15)), "text": "One lift tonight"}
    msg = _post(SPLIT_TEXT, [], replies=[reply])
    corrections = {f"{CH}:{msg.ts}:late": {"ok": True}}
    result = build_lineage([msg], [], LOCS, [], cfg, corrections)
    assert result.sessions[0].needs_review is True


def test_false_merge_correction_wins_over_true_and_negated_language(cfg):
    reply = {"ts": _ts(datetime(2099, 7, 16, 15)),
             "text": "Combined details for both slots; the group is too large for one lift."}
    msg = _post(SPLIT_TEXT, [], replies=[reply])
    key = f"{CH}:{msg.ts}"
    corrections = {key: {"merged": True}, key + ":late": {"merged": False}}
    assert [s.format for s in build_lineage([msg], [], LOCS, [], cfg, corrections).sessions] == ["split", "split"]


def test_missing_app_post_remains_reviewable_and_consumed_post_not_parsed_twice(cfg):
    msg = _post(SPLIT_TEXT, [R("white_check_mark", "UFAKE1")])
    practice = AppPractice(900, datetime(2099, 7, 16, 18, 15), "cancelled", False,
                           CH, msg.ts, None, "Balance Fitness Studio", None,
                           button_rsvp_uids=("UFAKE2", BOT))
    result = build_lineage([msg], [practice], LOCS, [], cfg)
    assert len(result.sessions) == 1
    assert (result.sessions[0].status, result.sessions[0].rsvp_count) == ("cancelled", 2)
    result = build_lineage([replace(msg, deleted=True)], [practice], LOCS, [], cfg)
    assert len(result.sessions) == 1
    assert result.sessions[0].rsvp_count == 1
    assert "post_missing" in result.sessions[0].flags and result.sessions[0].needs_review


@pytest.mark.parametrize("clock, expected", [
    ("10:15", "22:15:00"), ("12:15", "12:15:00"),
    ("6:15 AM", "06:15:00"), ("18:15", "18:15:00"),
])
def test_merge_reply_clock_uses_pm_unless_explicit(cfg, clock, expected):
    msg = _post(SPLIT_TEXT, [], replies=[{
        "ts": _ts(datetime(2099, 7, 16, 15)), "text": f"One session at {clock}"}])
    result = build_lineage([msg], [], LOCS, [], cfg)
    assert result.sessions[0].start_time.isoformat() == expected


def test_build_is_repeatable_and_does_not_mutate_inputs(cfg):
    from copy import deepcopy
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1")])
    corrections = {f"{CH}:{msg.ts}": {"activities": ["Run"], "rsvp_emoji": ["zap"],
                                     "plan_emoji": ["book"], "merged": True}}
    before = deepcopy((msg, corrections, cfg, LOCS))
    first = build_lineage([msg], [], LOCS, [], cfg, corrections)
    second = build_lineage([msg], [], LOCS, [], cfg, corrections)
    assert first == second
    assert (msg, corrections, cfg, LOCS) == before


def test_consumed_posts_are_indexed_by_channel_and_timestamp(cfg):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1")])
    other = replace(msg, channel_id="C03FKTTHNHW")
    practice = AppPractice(900, datetime(2099, 7, 16, 18, 15), "scheduled", False,
                           CH, msg.ts, "six", "Balance Fitness Studio", None)
    result = build_lineage([other, msg], [practice], LOCS, [], cfg)
    assert len(result.sessions) == 3
    assert len([s for s in result.sessions if s.era == "template"]) == 2


@pytest.mark.parametrize("suffix", ["", ":early", ":late", ":merged", ":2099-07-16"])
def test_possible_misses_exclude_corrected_posts_and_session_keys(cfg, suffix):
    msg = _post("Invented reminder", [R("six", *[f"UFAKE{i}" for i in range(6)])])
    key = f"{CH}:{msg.ts}"
    assert build_lineage([msg], [], LOCS, [], cfg).possible_misses == [key]
    assert build_lineage([msg], [], LOCS, [], cfg, {key + suffix: {"skip": True}}).possible_misses == []


def test_skipped_template_does_not_become_possible_miss(cfg):
    msg = _post(SPLIT_TEXT, [R("six", *[f"UFAKE{i}" for i in range(6)])])
    key = f"{CH}:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {"skip": True}})
    assert result.sessions == [] and result.possible_misses == []


@pytest.mark.parametrize("slot", ["early", "late"])
def test_correction_rsvp_defaults_slot_and_honors_explicit_slot_and_emoji(cfg, slot):
    msg = _post(SPLIT_TEXT, [])
    key = f"{CH}:{msg.ts}:{slot}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {"add": [
        {"slack_uid": "UFAKEDEFAULT", "role": "rsvp"},
        {"slack_uid": "UFAKEOVERRIDE", "role": "rsvp", "slot": "late", "emoji": "seven"},
        {"slack_uid": "UFAKELEAD", "role": "lead"},
    ]}})
    rows = {row.slack_uid: row for row in result.attendance}
    assert (rows["UFAKEDEFAULT"].slot, rows["UFAKEDEFAULT"].emoji) == (slot, None)
    assert (rows["UFAKEOVERRIDE"].slot, rows["UFAKEOVERRIDE"].emoji) == ("late", "seven")
    assert rows["UFAKELEAD"].slot is None


@pytest.mark.parametrize("emojis", [("ski", "snowflake"), ("runner", "skier", "bike")])
@pytest.mark.parametrize("override", [None, ["white_check_mark"], []])
def test_ambiguous_choices_union_rsvps_and_correction_overrides(cfg, emojis, override):
    text = ("Thursday, Jul 16, 2099\nEasy Run @ Theodore Wirth Trails\nTime: 6:15 PM\nBop that "
            + " or ".join(f":{emoji}: (choice)" for emoji in emojis))
    msg = _post(text, [R(emoji, "UFAKE0001", f"UFAKE000{i + 2}") for i, emoji in enumerate(emojis)]
                + [R("white_check_mark", "UFAKE0009")])
    corrections = {} if override is None else {f"{CH}:{msg.ts}": {"rsvp_emoji": override}}
    result = build_lineage([msg], [], LOCS, [], cfg, corrections)
    assert len(result.sessions) == 1
    session = result.sessions[0]
    expected = ({"UFAKE0001", "UFAKE0002", "UFAKE0003"} if len(emojis) == 2 else
                {"UFAKE0001", "UFAKE0002", "UFAKE0003", "UFAKE0004"})
    if override is not None:
        expected = {"UFAKE0009"} if override else set()
    assert {a.slack_uid for a in result.attendance if a.role == "rsvp"} == expected
    assert session.rsvp_count == len(expected)
    assert session.format == "single"
    assert "emoji_ambiguous" in session.flags
    assert session.needs_review == (override is None)


@pytest.mark.parametrize("merged", [False, True])
def test_button_rsvps_keep_each_source_session_slot(cfg, merged):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE0001")])
    early = AppPractice(9901, datetime(2099, 7, 16, 18, 5), "scheduled", False,
                        CH, msg.ts, "six", "Balance Fitness Studio", None,
                        activities=("Strength",), button_rsvp_uids=("UFAKE0001", "UFAKE0002", "UFAKE0004"))
    late = replace(early, id=9902, date=datetime(2099, 7, 16, 19, 20), slack_session_emoji="seven",
                   button_rsvp_uids=("UFAKE0001", "UFAKE0003", "UFAKE0004"))
    result = build_lineage([msg], [late, early], LOCS, [], cfg,
                           {"practice:9901": {"merged": merged}})
    assert [s.format for s in result.sessions] == (["merged"] if merged else ["split", "split"])
    assert {(r.slack_uid, r.slot) for r in result.attendance if r.source == "button"} == {
        ("UFAKE0002", "early"), ("UFAKE0003", "late"), ("UFAKE0004", "early"),
        ("UFAKE0004", "late"), ("UFAKE0001", "late")}
    assert [s.rsvp_count for s in result.sessions] == ([4] if merged else [3, 3])


def test_slot_preservation_keeps_nonnull_emoji_identity(cfg):
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE0001")])
    corrections = {f"{CH}:{msg.ts}:early": {"add": [
        {"slack_uid": "UFAKE0001", "role": "rsvp", "emoji": "six", "slot": "late"}]}}
    result = build_lineage([msg], [], LOCS, [], cfg, corrections)
    # Non-null emoji rows still obey the persisted unique constraint.
    rsvps = [r for r in result.attendance if r.role == "rsvp"]
    assert [(r.slack_uid, r.emoji, r.slot) for r in rsvps] == [("UFAKE0001", "six", "early")]


GEN = "C0B2VN1LU11"


def _event_post(text, reactions, channel=GEN, when=datetime(2099, 5, 1, 9, 0)):
    ts = _ts(when)
    return ArchivedMessage(channel, ts, {"ts": ts, "text": text, "reactions": reactions})


def test_created_event_uses_correction_date_not_post_ts(cfg):
    msg = _event_post("*Kickoff potluck!*\nReact :white_check_mark: or :x:",
                      [R("white_check_mark", "UFAKE0001", "UFAKE0002"), R("x", "UFAKE0003"),
                       R("tada", "UFAKE0004")])
    key = f"{GEN}:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-14", "category": "kickoff", "title": "Kickoff potluck",
        "emoji_roles": {"white_check_mark": "rsvp", "x": "decline"}}})
    session, = result.sessions
    assert (session.date, session.kind, session.category, session.title) == (
        date(2099, 5, 14), "event", "kickoff", "Kickoff potluck")
    assert session.rsvp_count == 2
    roles = sorted((row.slack_uid, row.role) for row in result.attendance)
    assert roles == [("UFAKE0001", "rsvp"), ("UFAKE0002", "rsvp"), ("UFAKE0003", "decline")]


def test_multi_option_post_counts_every_option_once(cfg):
    msg = _event_post("Race :runner: or cheer :mega:",
                      [R("runner", "UFAKE0001", "UFAKE0002"), R("mega", "UFAKE0002", "UFAKE0003")],
                      channel="C02HXN45214")
    key = f"C02HXN45214:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-20", "category": "race",
        "emoji_roles": {"runner": "rsvp", "mega": "rsvp"}}})
    assert result.sessions[0].rsvp_count == 3


def test_count_only_session(cfg):
    msg = _event_post("Old kickoff\n*May 1, 2099 9:43 AM* · :white_check_mark: 40 :x: 17", [])
    key = f"{GEN}:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-16", "category": "kickoff", "reported_count": 40}})
    session, = result.sessions
    assert (session.rsvp_count, session.reported_count) == (40, 40)
    assert "identities_lost" in session.flags and session.needs_review is False
    assert result.attendance == []


def test_event_channel_posts_never_parse_as_templates(cfg):
    text = "_Thursday, Jul 16th, 2099_ • _TCSC_\n*Board meeting @ Somewhere*\n*Time:* 6:00 PM"
    msg = _event_post(text, [R("white_check_mark", "UFAKE0001")])
    assert build_lineage([msg], [], LOCS, [], cfg).sessions == []


@pytest.mark.parametrize("kind,activities,override,expected", [
    ("practice", [], None, "practice"),
    ("practice", [], "social", "practice"),     # practices are always category practice
    ("event", ["Kickoff"], None, "kickoff"),
    ("event", [], None, "other"),
    ("event", [], "board", "board"),
    ("event", [], "practice", "other"),
    ("trip", [], None, "trip"),
])
def test_session_category(kind, activities, override, expected):
    draft = SessionDraft("k", "g", "template", date(2099, 1, 1), None, "t",
                         kind=kind, activities=activities, category=override or "")
    assert session_category(draft) == expected
