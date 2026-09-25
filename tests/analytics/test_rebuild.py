from unittest.mock import patch

import pytest

from app.analytics.drafts import AttendanceDraft
from app.analytics.history_config import HistoryConfigError
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.analytics.rebuild import rebuild, resolve_people
from app.analytics.archive import upsert_message

CH = "C042G463AQ1"
TEXT = ("_Thursday, Jul 16th, 2099_ • _TCSC_\n*Strength Circuit @ Balance Fitness Studio*\n"
        "*Time:* 6:05 PM :six: & 7:20 PM :seven:\n*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*")


def _seed():
    upsert_message(CH, {"ts": "4087911600.000100", "text": TEXT, "reactions": [
        {"name": "six", "count": 2, "users": ["UFAKE1", "UFAKE2"]},
        {"name": "seven", "count": 1, "users": ["UFAKE3"]}]})


def test_rebuild_writes_sessions_and_is_repeatable(db_session):
    _seed()
    first = rebuild(commit=False)
    keys1 = sorted(s.session_key for s in PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%")))
    second = rebuild(commit=False)
    keys2 = sorted(s.session_key for s in PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%")))
    assert keys1 == keys2 == [f"{CH}:4087911600.000100:early", f"{CH}:4087911600.000100:late"]
    assert first["sessions"] == second["sessions"]
    early = PracticeSession.query.filter_by(session_key=keys1[0]).one()
    assert early.rsvp_count == 2 and early.format == "split"
    assert PracticeAttendance.query.filter_by(session_id=early.id, role="rsvp").count() == 2


def test_invalid_config_leaves_tables_untouched(db_session):
    _seed()
    rebuild(commit=False)
    before = PracticeSession.query.count()
    with patch("app.analytics.rebuild.load_history_config", side_effect=HistoryConfigError("bad")):
        with pytest.raises(HistoryConfigError):
            rebuild(commit=False)
    assert PracticeSession.query.count() == before

def test_rebuild_applies_db_corrections(db_session):
    from app.analytics.corrections import upsert_correction
    _seed()
    upsert_correction(f"{CH}:4087911600.000100", {"merged": True}, "test merge", "test")
    rebuild(commit=False)
    s = PracticeSession.query.filter_by(session_key=f"{CH}:4087911600.000100:merged").one()
    assert s.format == "merged" and s.rsvp_count == 3


def test_load_inputs_archive_threads_and_deleted_rows(db_session):
    from datetime import datetime
    from app.analytics.rebuild import load_inputs

    parent = upsert_message(CH, {"ts": "4087911601.000100", "thread_ts": "4087911601.000100", "text": "parent"})
    for ts in ["4087911603.000100", "4087911602.000100"]:
        upsert_message(CH, {"ts": ts, "thread_ts": parent.ts, "text": "reply"})
    deleted = upsert_message(CH, {"ts": "4087911604.000100", "thread_ts": parent.ts, "text": "deleted reply"})
    deleted.deleted_at = datetime.utcnow()
    gone = upsert_message(CH, {"ts": "4087911605.000100", "text": "deleted parent"})
    gone.deleted_at = datetime.utcnow()
    upsert_message("CFAKEOTHER", {"ts": parent.ts, "text": "other channel"})
    messages, _, _, _ = load_inputs()
    indexed = {(m.channel_id, m.ts): m for m in messages}
    loaded = indexed[(CH, parent.ts)]
    assert loaded.archive_id == parent.id and not loaded.deleted
    assert [r["ts"] for r in loaded.replies] == ["4087911602.000100", "4087911603.000100"]
    assert indexed[(CH, gone.ts)].deleted
    assert ("CFAKEOTHER", parent.ts) not in indexed


def test_app_inputs_identity_and_db_coach_emoji(db_session):
    from datetime import date, datetime
    from dataclasses import replace
    from app.models import AppConfig, Season, SlackUser, User
    from app.practices.models import Practice, PracticeActivity, PracticeLead, PracticeLocation, PracticeRSVP, PracticeType
    from app.analytics.history_config import load_history_config
    from app.analytics.rebuild import load_inputs

    users = []
    for index in range(4):
        slack = SlackUser(slack_uid=f"UFAKE9{index}")
        user = User(first_name="Fake", last_name="Tester", email=f"analytics9-{index}@example.invalid", slack_user=slack)
        db_session.add(user)
        users.append(user)
    location = PracticeLocation(name="Task 9 test venue", spot="Test spot", latitude=45.0, longitude=-93.0)
    practice = Practice(date=datetime(2099, 7, 17, 18, 5), day_of_week="Friday",
        location=location, activities=[PracticeActivity(name="Task 9 activity")],
        practice_types=[PracticeType(name="Task 9 type")],
        slack_channel_id=CH, slack_message_ts="4087911606.000100",
        plan_reactions=[{"emoji": "test_plan", "label": "Test plan"}])
    season = Season(name="Task 9 summer", season_type="summer", year=2099,
                    start_date=date(2099, 7, 1), end_date=date(2099, 8, 1))
    legacy = Season(name="Task 9 legacy", season_type="legacy", year=2099,
                    start_date=date(2099, 7, 1), end_date=date(2099, 8, 1))
    db_session.add_all([practice, season, legacy])
    db_session.flush()
    db_session.add_all([
        PracticeLead(practice_id=practice.id, user_id=users[0].id, role="lead"),
        PracticeLead(practice_id=practice.id, user_id=users[1].id, role="coach"),
        PracticeRSVP(practice_id=practice.id, user_id=users[2].id, status="going", slack_user_id="UFAKEWRONG"),
        PracticeRSVP(practice_id=practice.id, user_id=users[3].id, status="maybe"),
    ])
    AppConfig.set("analytics_coach_emoji", ["test_coach"])
    upsert_message(CH, {"ts": practice.slack_message_ts, "text": "Test practice", "reactions": [
        {"name": "test_coach", "count": 1, "users": ["UFAKE93"]},
        {"name": "test_plan", "count": 1, "users": ["UFAKEUNKNOWN"]}]})
    _, practices, locations, seasons = load_inputs()
    draft = next(p for p in practices if p.id == practice.id)
    assert draft.lead_uids == ("UFAKE90",)
    assert draft.coach_uids == ("UFAKE91",)
    assert draft.button_rsvp_uids == ("UFAKE92",)
    assert draft.plan_emoji == ("test_plan",)
    assert draft.activities == ("Task 9 activity",) and draft.types == ("Task 9 type",)
    assert draft.location_name == location.name and draft.location_spot == location.spot
    assert next(loc for loc in locations if loc.id == location.id).lat == 45.0
    assert season.name in [s.name for s in seasons] and legacy.name not in [s.name for s in seasons]
    cfg = replace(load_history_config(), coach_emoji=frozenset({"wrong_emoji"}))
    rebuild(cfg=cfg, commit=False)
    session = PracticeSession.query.filter_by(practice_id=practice.id).one()
    assert session.season_label == season.name and session.start_time == practice.date.time()
    assert session.location_id == location.id and session.rsvp_count == 1
    attendance = PracticeAttendance.query.filter_by(session_id=session.id).all()
    assert {(r.slack_uid, r.role, r.user_id) for r in attendance} == {
        ("UFAKE90", "lead", users[0].id), ("UFAKE91", "coach", users[1].id),
        ("UFAKE92", "rsvp", users[2].id), ("UFAKE93", "coach", users[3].id),
        ("UFAKEUNKNOWN", "plan", None)}
    assert cfg.coach_emoji == frozenset({"wrong_emoji"})


@pytest.mark.parametrize("failure", ["attendance", "weather"])
def test_rebuild_failure_restores_previous_tables(app, monkeypatch, failure):
    import sys
    from types import SimpleNamespace
    from sqlalchemy.orm import scoped_session, sessionmaker
    from app.models import db

    # Session commits/rollbacks use savepoints inside a test-owned transaction.
    with app.app_context(), db.engine.connect() as connection:
        transaction = connection.begin()
        session = scoped_session(sessionmaker(bind=connection, join_transaction_mode="create_savepoint"))
        monkeypatch.setattr(db, "session", session)
        monkeypatch.setitem(sys.modules, "app.analytics.weather", SimpleNamespace(apply_weather=lambda rows: None))
        try:
            _seed()
            rebuild()  # Exercise commit=True without persisting test fixtures.
            before = [(s.id, s.session_key) for s in PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%"))]
            ids = [row[0] for row in before]
            attendees = [(r.id, r.slack_uid) for r in PracticeAttendance.query.filter(PracticeAttendance.session_id.in_(ids))]
            if failure == "weather":
                def fail_weather(rows):
                    assert rows and all(row.id for row in rows)
                    raise RuntimeError("weather failed")
                monkeypatch.setitem(sys.modules, "app.analytics.weather", SimpleNamespace(apply_weather=fail_weather))
            else:
                from app.analytics.lineage import build_lineage
                from dataclasses import replace
                def bad_attendance(*args, **kwargs):
                    result = build_lineage(*args, **kwargs)
                    result.attendance[0] = replace(result.attendance[0], role="bad_role")
                    return result
                monkeypatch.setattr("app.analytics.rebuild.build_lineage", bad_attendance)
            with pytest.raises(Exception, match="weather failed|ck_attendance_role"):
                rebuild(commit=False)
            assert [(s.id, s.session_key) for s in PracticeSession.query.filter(PracticeSession.id.in_(ids))] == before
            assert [(r.id, r.slack_uid) for r in PracticeAttendance.query.filter(PracticeAttendance.session_id.in_(ids))] == attendees
        finally:
            session.remove()
            transaction.rollback()


def test_flags_and_draft_fields_are_persisted(db_session):
    from datetime import datetime
    from app.analytics.rebuild import flagged_sessions

    _seed()
    start = datetime.utcnow()
    stats = rebuild(commit=False)
    rows = PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%")).all()
    flagged = flagged_sessions()
    assert [s.date for s in flagged] == sorted(s.date for s in flagged)
    assert all(s.needs_review for s in flagged)
    assert stats["needs_review"] == len(flagged)
    assert set(stats) == {"sessions", "attendance", "needs_review", "possible_misses",
                          "candidates", "empty_weeks"}
    for row in rows:
        archive = db_session.get(SlackArchiveMessage, row.source_message_id)
        assert archive.ts == "4087911600.000100"
        assert row.day_of_week == row.date.strftime("%A")
        assert row.rebuilt_at >= start and row.rebuilt_at.tzinfo is None
        assert row.activities and row.workout_types
        assert (row in flagged) == row.needs_review


def test_rebuild_uses_rsvp_from_and_flushes_weather(db_session, monkeypatch):
    import sys
    from types import SimpleNamespace
    from app.analytics.corrections import upsert_correction

    _seed()
    target_ts = "4087911607.000100"
    upsert_message(CH, {"ts": target_ts, "thread_ts": "4087911600.000100",
        "text": "Additional responses", "reactions": [
            {"name": "six", "count": 1, "users": ["UFAKEEXTRA"]}]})
    upsert_correction(f"{CH}:4087911600.000100:early", {"rsvp_from": [f"{CH}:{target_ts}"]},
                      "include thread responses", "test")
    seen = []
    def weather(rows):
        seen.extend(rows)
        for row in rows:
            if row.session_key == f"{CH}:4087911600.000100:early":
                row.temp_f = 42.5
    monkeypatch.setitem(sys.modules, "app.analytics.weather", SimpleNamespace(apply_weather=weather))
    rebuild(commit=False)
    db_session.expire_all()
    early = PracticeSession.query.filter_by(session_key=f"{CH}:4087911600.000100:early").one()
    assert early.rsvp_count == 3 and early.temp_f == 42.5
    assert early.id in [row.id for row in seen]
    assert PracticeAttendance.query.filter_by(session_id=early.id, slack_uid="UFAKEEXTRA").one().user_id is None


PEOPLE = {"uid_to_user": {"UFAKE0001": 11, "UFAKE0002": 12},
          "name_to_member": {"pat example": (11, "UFAKE0001"), "no slack": (13, None)}}


def _row(uid=None, name=None, key="trip:cuyuna:2099", role="signup"):
    return AttendanceDraft(key, uid, role, None, None, "reaction", name)


def test_resolve_people_preserves_button_rsvp_slots():
    drafts = [AttendanceDraft("practice:999:merged", "UFAKE0001", "rsvp", None, slot, "button")
              for slot in ("early", "late")]
    rows = resolve_people(drafts, PEOPLE)
    assert len(rows) == 2
    assert {row["slot"] for row in rows} == {"early", "late"}
    assert all(row["person_key"] == "slack:UFAKE0001" for row in rows)


def test_resolve_people_matches_names_and_dedupes():
    rows = resolve_people([_row(name="pat example"), _row(uid="UFAKE0001"),   # same person twice
                           _row(name="no slack"), _row(name="nobody here"),
                           _row(uid="UFAKE0002", key="C1:1.0:main", role="rsvp")], PEOPLE)
    got = sorted((r["session_key"], r["person_key"], r["user_id"], r["unmatched"]) for r in rows)
    assert got == [("C1:1.0:main", "slack:UFAKE0002", 12, False),
                   ("trip:cuyuna:2099", "name:nobody here", None, True),
                   ("trip:cuyuna:2099", "slack:UFAKE0001", 11, False),
                   ("trip:cuyuna:2099", "user:13", 13, False)]


def test_ambiguous_name_stays_unmatched():
    rows = resolve_people([_row(name="pat example", uid="UFAKE0002")],
                          {"uid_to_user": {"UFAKE0002": 12}, "name_to_member": {}})
    assert rows[0]["person_key"] == "slack:UFAKE0002"          # lone-mention fallback
    rows = resolve_people([_row(name="pat example")], {"uid_to_user": {}, "name_to_member": {}})
    assert rows[0]["person_key"] == "name:pat example" and rows[0]["unmatched"]


def test_resolve_people_keeps_mention_when_matched_member_has_no_slack():
    row = resolve_people([_row(name="no slack", uid="UFAKE0009")], PEOPLE)[0]
    assert (row["person_key"], row["slack_uid"], row["user_id"], row["unmatched"]) == (
        "slack:UFAKE0009", "UFAKE0009", 13, False)


@pytest.mark.parametrize("uid", [None, "UFAKE0001"])
def test_resolve_people_known_user_skips_name_matching(uid):
    draft = AttendanceDraft("trip:cuyuna:2099", uid, "signup", None, None,
                            "app", "pat example", user_id=13)
    row = resolve_people([draft], PEOPLE)[0]
    assert row["user_id"] == 13 and not row["unmatched"]
    assert row["person_key"] == ("slack:UFAKE0001" if uid else "user:13")


def _register_trip(db_session, user):
    from datetime import datetime
    from app.models import Trip
    from app.trips.models import TripRegistration, TripSeries

    series = TripSeries(slug="cuyuna", name="Fake trip", destination="Fake venue")
    trip = Trip(slug="task6-fix-trip-2099", series=series, name="Fake trip", destination="Fake venue",
                max_participants_standard=10, max_participants_extra=0,
                start_date=datetime(2099, 9, 25, 12), end_date=datetime(2099, 9, 27, 12),
                signup_start=datetime(2099, 7, 1), signup_end=datetime(2099, 9, 1),
                price_low=0, price_high=0)
    registration = TripRegistration(trip=trip, user=user, status="confirmed",
                                    price_tier="low", amount_cents=0)
    db_session.add(registration)
    db_session.flush()


@pytest.mark.parametrize("uid", [None, "UFAKE6002"])
def test_rebuild_trip_count_dedupes_typed_name_and_app_registration(db_session, uid):
    from app.models import SlackUser, User

    user = User(first_name="Pat", last_name="Example", email="task6-overlap@example.invalid",
                slack_user=SlackUser(slack_uid=uid) if uid else None)
    _register_trip(db_session, user)
    upsert_message("C068ECRE0PQ", {"ts": "4087911703.000100", "subtype": "bot_message",
        "username": "Cuyuna Trip Sign-Up",
        "text": "Trip Signup Submitted. This does not mean that they have paid!\nPat Example"})
    rebuild(commit=False)
    session = PracticeSession.query.filter_by(session_key="trip:cuyuna:2099").one()
    assert session.rsvp_count == 1
    row = PracticeAttendance.query.filter_by(session_id=session.id).one()
    assert row.user_id == user.id
    assert row.person_key == (f"slack:{uid}" if uid else f"user:{user.id}")


def test_rebuild_app_trip_retains_user_with_ambiguous_name_and_no_slack(db_session):
    from app.models import User

    user = User(first_name="Pat", last_name="Twin", email="task6-registered-twin@example.invalid")
    db_session.add(User(first_name="Pat", last_name="Twin", email="task6-other-twin@example.invalid"))
    _register_trip(db_session, user)
    rebuild(commit=False)
    session = PracticeSession.query.filter_by(session_key="trip:cuyuna:2099").one()
    row = PracticeAttendance.query.filter_by(session_id=session.id).one()
    assert row.person_key == f"user:{user.id}" and row.user_id == user.id
    assert row.slack_uid is None and row.source == "app"
    assert "unmatched_person" not in session.flags


def test_rebuild_dated_trip_unmatched_name_does_not_need_review(db_session):
    from app.analytics.corrections import upsert_correction

    upsert_message("C068ECRE0PQ", {"ts": "4087911704.000100", "subtype": "bot_message",
        "username": "Cuyuna Trip Sign-Up",
        "text": "Trip Signup Submitted. This does not mean that they have paid!\nZed Nobodyfake"})
    upsert_correction("trip:cuyuna:2099", {"date": "2099-09-25"}, "test date", "test")
    rebuild(commit=False)
    session = PracticeSession.query.filter_by(session_key="trip:cuyuna:2099").one()
    assert "unmatched_person" in session.flags
    assert "missing_date" not in session.flags and session.needs_review is False
    row = PracticeAttendance.query.filter_by(session_id=session.id).one()
    assert row.person_key == "name:zed nobodyfake" and row.user_id is None


def test_rebuild_events_trips_and_coverage_snapshot(db_session):
    from app.analytics.corrections import upsert_correction
    from app.models import AppConfig

    gen, trip = "C0B2VN1LU11", "C068ECRE0PQ"
    upsert_message(gen, {"ts": "4087911700.000100", "text": "Game night, give a :white_check_mark:",
                         "reactions": [{"name": "white_check_mark", "count": 1, "users": ["UFAKE7001"]},
                                       {"name": "x", "count": 1, "users": ["UFAKE7002"]}]})
    upsert_message(gen, {"ts": "4087911701.000100", "text": "Bop the :pickle: for pickleball",
                         "reactions": [{"name": "pickle", "count": 2, "users": ["UFAKE7003", "UFAKE7004"]}]})
    upsert_message(trip, {"ts": "4087911702.000100", "subtype": "bot_message",
                          "username": "Cuyuna Trip Sign-Up",
                          "text": "Trip Signup Submitted. This does not mean that they have paid!\nZed Nobodyfake"})
    upsert_correction(f"{gen}:4087911700.000100", {
        "create": True, "date": "2099-07-20", "category": "social", "title": "Game night",
        "emoji_roles": {"white_check_mark": "rsvp", "x": "decline"}}, "test", "test")
    stats = rebuild(commit=False)

    event = PracticeSession.query.filter_by(session_key=f"{gen}:4087911700.000100:main").one()
    assert (event.kind, event.category, event.rsvp_count) == ("event", "social", 1)
    decline = PracticeAttendance.query.filter_by(session_id=event.id, role="decline").one()
    assert decline.person_key == "slack:UFAKE7002"

    trip_session = PracticeSession.query.filter_by(session_key="trip:cuyuna:2099").one()
    row = PracticeAttendance.query.filter_by(session_id=trip_session.id).one()
    assert row.person_key == "name:zed nobodyfake" and row.slack_uid is None
    assert "unmatched_person" in trip_session.flags and "missing_date" in trip_session.flags

    keys = [c["post_key"] for c in AppConfig.get("analytics_coverage")["candidates"]]
    assert f"{gen}:4087911701.000100" in keys and f"{gen}:4087911700.000100" not in keys
    assert stats["candidates"] == len(keys)


def test_load_people_excludes_ambiguous_names(db_session):
    from app.analytics.rebuild import load_people
    from app.models import User

    for index, (first, last) in enumerate([("Pat", "Twin"), ("Pat", "Twin"), ("Solo", "Fake")]):
        db_session.add(User(first_name=first, last_name=last,
                            email=f"task6-person-{index}@example.invalid"))
    people = load_people()
    assert "pat twin" not in people["name_to_member"]
    assert "solo fake" in people["name_to_member"]


def test_load_app_trip_signups_keeps_members_without_slack_and_skips_cancelled(db_session):
    from datetime import date, datetime
    from app.analytics.drafts import TripSignup
    from app.analytics.rebuild import load_app_trip_signups
    from app.models import SlackUser, Trip, User
    from app.trips.models import TripRegistration, TripSeries

    series = TripSeries(slug="task6-fake-trip", name="Fake trip", destination="Fake venue")
    trip = Trip(slug="task6-fake-trip-2099", series=series, name="Fake trip", destination="Fake venue",
                max_participants_standard=10, max_participants_extra=0,
                start_date=datetime(2099, 1, 10, 12), end_date=datetime(2099, 1, 12, 12),
                signup_start=datetime(2098, 11, 1), signup_end=datetime(2099, 1, 1),
                price_low=0, price_high=0)
    registrations = []
    for index, status in enumerate(["confirmed", "pending_payment", "cancelled"]):
        user = User(first_name="Trip", last_name=f"Fake{index}",
                    email=f"task6-trip-{index}@example.invalid",
                    slack_user=SlackUser(slack_uid="UFAKE6001") if index == 0 else None)
        registrations.append(TripRegistration(trip=trip, user=user, status=status,
                                              price_tier="low", amount_cents=0))
    db_session.add_all(registrations)
    db_session.flush()
    rows = [row for row in load_app_trip_signups() if row.series_slug == series.slug]
    assert rows == [
        TripSignup(series.slug, 2098, date(2099, 1, 10), "UFAKE6001", None,
                   f"trip_registration:{registrations[0].id}", registrations[0].user_id),
        TripSignup(series.slug, 2098, date(2099, 1, 10), None, None,
                   f"trip_registration:{registrations[1].id}", registrations[1].user_id),
    ]


def test_coverage_snapshot_summarizes_candidates_in_central_time(db_session):
    from datetime import date, datetime
    from app.analytics.rebuild import coverage_snapshot

    row = upsert_message("C0B2VN1LU11", {"ts": "4087911710.000100",
        "text": "\n  \n" + "A" * 150 + "\nSecond line", "reactions": [
            {"name": "one", "count": 1}, {"name": "four", "count": 4},
            {"name": "two", "count": 2}, {"name": "three", "count": 3}]})
    row.posted_at = datetime(2099, 7, 20, 2)
    key = f"{row.channel_id}:{row.ts}"
    start = datetime.utcnow().replace(microsecond=0)
    snapshot = coverage_snapshot([key], [date(2099, 11, 9)])
    assert start <= datetime.fromisoformat(snapshot["computed_at"]) <= datetime.utcnow()
    assert snapshot["empty_weeks"] == ["2099-11-09"]
    assert snapshot["candidates"] == [{
        "post_key": key, "channel": "C0B2VN1LU11", "date": "2099-07-19",
        "text": "A" * 140, "reactions": {"four": 4, "three": 3, "two": 2}}]
