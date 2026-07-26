"""Candidate ranking for the lead picker.

Dates use year 2099 and user/location names carry a "TEST " prefix (with a
unique email suffix) per tests/practices/conftest.py -- this suite runs
against the real local dev database, and the brief's own example dates
(August 2026) are now the real near future, so they can't be used here
without risking a collision with real practice data. See
tests/practices/test_availability_service.py for the same convention.

eligible_leads() is a live, unscoped query over all PRACTICES_LEAD /
PRACTICES_DIRECTOR / HEAD_COACH / ASSISTANT_COACH tagged users, so assertions
use membership/subset checks against the rows this test created rather than
asserting the full result set -- a real tagged member showing up in the dev
DB must not make this suite start failing.
"""

import uuid
from datetime import date, datetime, timedelta

from app.models import Tag, User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.lead_candidates import lead_candidates
from app.practices.models import Practice, PracticeLead, PracticeLocation


def _lead_user(name):
    tag = Tag.query.filter_by(name="PRACTICES_LEAD").first()
    if tag is None:
        tag = Tag(name="PRACTICES_LEAD", display_name="Practices Lead")
        db.session.add(tag)
        db.session.flush()
    unique = uuid.uuid4().hex[:8]
    user = User(first_name=f"TEST {name}", last_name="Candidate",
                email=f"test-leadcand-{name.lower()}-{unique}@example.invalid")
    user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user


def _practice(day, location_id=None):
    p = Practice(date=datetime(2099, 8, day, 18, 15), day_of_week="Tuesday",
                 leads_needed=2, location_id=location_id)
    db.session.add(p)
    db.session.flush()
    return p


def _open_poll(practice):
    poll = LeadAvailabilityPoll(
        starts_on=date(2099, 8, 1), ends_on=date(2099, 8, 31),
        channel_id="C1", message_ts="1.1", status=PollStatus.OPEN,
        opened_at=datetime(2099, 8, 1),
    )
    db.session.add(poll)
    db.session.flush()
    db.session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji="letter_a", position=0))
    db.session.flush()
    return poll


def _available(poll, practice, user, *, snapshot=True):
    db.session.add(LeadAvailabilityResponse(
        poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction",
        answered_for_date=practice.date if snapshot else datetime(2020, 1, 1),
        answered_for_location_id=practice.location_id if snapshot else None,
    ))
    db.session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=user.id, status=ParticipantStatus.RESPONDED))
    db.session.flush()


def _cleanup(*, users=(), practices=(), polls=(), locations=()):
    """FK-safe teardown, in an order that survives a poisoned session.

    Rolls back first so a prior failed statement doesn't turn this cleanup
    itself into a PendingRollbackError that leaves debris behind for the next
    test to trip over. All ids passed in must already be plain ints captured
    before the caller's `try` block -- evaluating `obj.id` here, after a
    failed assertion, is exactly how test debris has leaked into the dev
    database before.

    Order: PracticeLead rows (they reference practices but nothing references
    them) -> polls (cascade deletes their poll-practice/participant/response
    rows, which reference both polls and practices) -> practices -> locations
    -> user tag links -> users.
    """
    db.session.rollback()

    practice_ids = list(practices)
    if practice_ids:
        PracticeLead.query.filter(
            PracticeLead.practice_id.in_(practice_ids)
        ).delete(synchronize_session=False)

    for poll_id in polls:
        obj = db.session.get(LeadAvailabilityPoll, poll_id)
        if obj is not None:
            db.session.delete(obj)
    db.session.flush()

    # ORM deletes, never a bulk .delete(): a bulk delete skips the
    # practice_types_junction rows and dies on the FK the moment _practice()
    # is given a practice_type, which would then leak ~4 practices, 2 users
    # and a poll per test into the shared dev database from inside a finally.
    for practice_id in practice_ids:
        stored = db.session.get(Practice, practice_id)
        if stored is not None:
            db.session.delete(stored)
    db.session.flush()
    if locations:
        PracticeLocation.query.filter(
            PracticeLocation.id.in_(list(locations))
        ).delete(synchronize_session=False)

    for user_id in users:
        obj = db.session.get(User, user_id)
        if obj is not None:
            obj.tags = []
    db.session.flush()
    for user_id in users:
        obj = db.session.get(User, user_id)
        if obj is not None:
            db.session.delete(obj)

    db.session.commit()


def test_available_sorts_before_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    quiet = _lead_user("Zoe")
    keen = _lead_user("Ada")
    _available(poll, practice, keen)
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    quiet_id, keen_id = quiet.id, keen.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert keen_id in by_id and quiet_id in by_id, \
            "unavailable people are ranked down, never removed"
        assert rows[0]["user_id"] == keen_id
        assert rows[0]["available"] is True
        assert by_id[quiet_id]["available"] is False
    finally:
        _cleanup(users=[quiet_id, keen_id], practices=[practice_id], polls=[poll_id])


def test_least_loaded_available_lead_comes_first(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    busy = _lead_user("Busy")
    fresh = _lead_user("Fresh")
    _available(poll, practice, busy)
    _available(poll, practice, fresh)

    others = []
    for day in (11, 13):
        other = _practice(day)
        db_session.add(PracticeLead(practice_id=other.id, user_id=busy.id, role="lead"))
        others.append(other)
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    busy_id, fresh_id = busy.id, fresh.id
    other_ids = [o.id for o in others]

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[fresh_id]["led_in_block"] == 0
        assert by_id[busy_id]["led_in_block"] == 2
        # Among these two, the least-loaded available lead ranks first.
        idx = [r["user_id"] for r in rows if r["user_id"] in (fresh_id, busy_id)]
        assert idx == [fresh_id, busy_id]
    finally:
        _cleanup(users=[busy_id, fresh_id], practices=[practice_id] + other_ids, polls=[poll_id])


def test_assist_rows_are_not_counted_as_load(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    other = _practice(11)
    db_session.add(PracticeLead(practice_id=other.id, user_id=user.id, role="assist"))
    db_session.commit()

    practice_id, poll_id, user_id, other_id = practice.id, poll.id, user.id, other.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["led_in_block"] == 0, \
            "the assist role is retired and must not count"
    finally:
        _cleanup(users=[user_id], practices=[practice_id, other_id], polls=[poll_id])


def test_response_is_stale_when_location_changed(db_session):
    location = PracticeLocation(name="TEST Wirth")
    db_session.add(location)
    db_session.flush()
    practice = _practice(4, location_id=location.id)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    moved = PracticeLocation(name="TEST Hyland")
    db_session.add(moved)
    db_session.flush()
    practice.location_id = moved.id
    db_session.commit()

    practice_id, poll_id, user_id = practice.id, poll.id, user.id
    location_id, moved_id = location.id, moved.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["stale"] is True, \
            "volunteering for Wirth is not volunteering for Hyland"
    finally:
        _cleanup(users=[user_id], practices=[practice_id], polls=[poll_id],
                 locations=[location_id, moved_id])


def test_workout_edit_does_not_make_a_response_stale(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    practice.workout_description = "TEST edited after they answered"
    db_session.commit()

    practice_id, poll_id, user_id = practice.id, poll.id, user.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["stale"] is False, \
            "only date/time and location decide availability; text edits must not warn"
    finally:
        _cleanup(users=[user_id], practices=[practice_id], polls=[poll_id])


def test_led_last_90d_anchors_to_practice_date_not_newest_lead_row(db_session):
    """led_last_90d must be anchored to practice.date, never to the newest
    matching PracticeLead row -- see the _load_counts docstring.

    One lead gets four role='lead' assignments at known offsets from the
    practice being scheduled: 106 days before (outside the trailing window),
    75 days before (inside), exactly on the anchor (inside, the upper
    boundary), and 5 days after (in the future relative to the practice --
    outside under the correct rule).

    The +5d offset is deliberately close to the anchor (not far, e.g. +17d):
    if anchoring shifted to "the newest matching row" (anchor' = anchor+5),
    the window would slide forward by only 5 days -- not enough to also
    push the -75d row out (it has a 15-day margin to the -90d boundary) --
    so the mutation nets a *different* count (3) instead of swapping one
    in-window row for another and coincidentally landing on the same count.
    That's what makes this assertion sensitive to the anchor rule rather
    than incidentally passing either way.
    """
    practice = _practice(20)
    anchor = practice.date
    user = _lead_user("Anchor")

    offsets = (-106, -75, 0, 5)
    lead_practice_ids = []
    for delta in offsets:
        p = Practice(date=anchor + timedelta(days=delta), day_of_week="Tuesday", leads_needed=2)
        db_session.add(p)
        db_session.flush()
        db_session.add(PracticeLead(practice_id=p.id, user_id=user.id, role="lead"))
        lead_practice_ids.append(p.id)
    db_session.commit()

    practice_id, user_id = practice.id, user.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["led_last_90d"] == 2, (
            "only the -75d and on-anchor rows fall in [practice.date - 90d, practice.date]; "
            "anchoring on the newest row instead of practice.date would count -75d out and "
            "+5d in, yielding 3 instead of 2"
        )
    finally:
        _cleanup(users=[user_id], practices=[practice_id] + lead_practice_ids)


def test_available_ties_break_on_led_last_90d(db_session):
    """Equal led_in_block must fall through to led_last_90d, not name.

    eligible_leads() itself queries `ORDER BY User.first_name`, so if the two
    candidates' names happened to already be alphabetical in the direction
    this test expects, a sort key that silently dropped led_last_90d would
    still produce the "right" order by coincidence (Python's sort is
    stable, so ties fall back to that original query order) and this test
    would pass either way. Naming the *lower*-load candidate alphabetically
    *later* ("ZFresh...") than the higher-load one ("ALoaded...") makes the
    two orderings disagree, so only a sort that genuinely consults
    led_last_90d produces the expected result.
    """
    practice = _practice(4)
    poll = _open_poll(practice)
    fresh = _lead_user("ZFreshNinety")
    loaded = _lead_user("ALoadedNinety")
    _available(poll, practice, fresh)
    _available(poll, practice, loaded)

    # Dated before the poll's Aug 1-31 block, so it never touches
    # led_in_block, but within the trailing 90-day window anchored on this
    # practice's Aug 4 date -- isolates led_last_90d as the only difference
    # between these two candidates.
    prior = Practice(date=datetime(2099, 7, 1, 18, 15), day_of_week="Tuesday", leads_needed=2)
    db_session.add(prior)
    db_session.flush()
    db_session.add(PracticeLead(practice_id=prior.id, user_id=loaded.id, role="lead"))
    db_session.commit()

    practice_id, poll_id, prior_id = practice.id, poll.id, prior.id
    fresh_id, loaded_id = fresh.id, loaded.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[fresh_id]["led_in_block"] == by_id[loaded_id]["led_in_block"] == 0, \
            "led_in_block must be tied for this to isolate the next sort key"
        assert by_id[fresh_id]["led_last_90d"] == 0
        assert by_id[loaded_id]["led_last_90d"] == 1
        # "ALoadedNinety" sorts before "ZFreshNinety" alphabetically, and
        # eligible_leads() returns them in that order -- so this specific
        # assertion only holds if led_last_90d, not name or query order,
        # decided the ranking.
        idx = [r["user_id"] for r in rows if r["user_id"] in (fresh_id, loaded_id)]
        assert idx == [fresh_id, loaded_id], \
            "equal led_in_block must fall through to led_last_90d as the tie-break"
    finally:
        _cleanup(users=[fresh_id, loaded_id], practices=[practice_id, prior_id], polls=[poll_id])


def test_available_ties_break_on_name(db_session):
    """With every numeric key tied, name must decide the final order.

    _lead_user() always gives distinct first_names, and eligible_leads()
    itself queries `ORDER BY User.first_name` -- so two candidates with
    different first_names would already arrive in name order before
    lead_candidates() ever sorts them, and a sort key that dropped `name`
    entirely would still pass by coincidence (stable sort preserves that
    incoming order). Giving both users the *same* first_name and differing
    only by last_name breaks that coincidence: eligible_leads()'s ORDER BY
    can't distinguish them at all, so only an explicit comparison on the
    full "first last" name can put them in the right order. The row with
    the alphabetically later last_name ("Zzz") is inserted first, biasing
    any accidental fallback to insertion/query order the wrong way.
    """
    practice = _practice(4)
    poll = _open_poll(practice)
    tag = Tag.query.filter_by(name="PRACTICES_LEAD").first()
    if tag is None:
        tag = Tag(name="PRACTICES_LEAD", display_name="Practices Lead")
        db_session.add(tag)
        db_session.flush()

    later = User(first_name="TEST Sameo", last_name="Zzz",
                 email=f"test-leadcand-later-{uuid.uuid4().hex[:8]}@example.invalid")
    later.tags = [tag]
    db_session.add(later)
    db_session.flush()

    earlier = User(first_name="TEST Sameo", last_name="Aaa",
                   email=f"test-leadcand-earlier-{uuid.uuid4().hex[:8]}@example.invalid")
    earlier.tags = [tag]
    db_session.add(earlier)
    db_session.flush()

    _available(poll, practice, later)
    _available(poll, practice, earlier)
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    earlier_id, later_id = earlier.id, later.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[earlier_id]["led_in_block"] == by_id[later_id]["led_in_block"] == 0, \
            "led_in_block must be tied for this to isolate the name tie-break"
        assert by_id[earlier_id]["led_last_90d"] == by_id[later_id]["led_last_90d"] == 0, \
            "led_last_90d must also be tied for this to isolate the name tie-break"
        assert by_id[earlier_id]["name"] == "TEST Sameo Aaa"
        assert by_id[later_id]["name"] == "TEST Sameo Zzz"
        idx = [r["user_id"] for r in rows if r["user_id"] in (earlier_id, later_id)]
        assert idx == [earlier_id, later_id], \
            "with every numeric key tied, name must decide the order"
    finally:
        _cleanup(users=[earlier_id, later_id], practices=[practice_id], polls=[poll_id])


def test_responded_flag_distinguishes_silence_from_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    silent = _lead_user("Silent")
    declined = _lead_user("Declined")
    db_session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=declined.id, status=ParticipantStatus.DONE))
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    silent_id, declined_id = silent.id, declined.id

    try:
        rows = {r["user_id"]: r for r in lead_candidates(practice)}
        assert rows[silent_id]["responded"] is False
        assert rows[declined_id]["responded"] is True
        assert rows[declined_id]["available"] is False
    finally:
        _cleanup(users=[silent_id, declined_id], practices=[practice_id], polls=[poll_id])


def _untagged_user(name):
    """A member with no eligible tag: absent from eligible_leads()."""
    unique = uuid.uuid4().hex[:8]
    user = User(first_name=f"TEST {name}", last_name="Outsider",
                email=f"test-leadcand-{name.lower()}-{unique}@example.invalid")
    db.session.add(user)
    db.session.flush()
    return user


def test_an_assigned_lead_outside_the_pool_still_appears(db_session):
    """Otherwise the next save deletes them.

    The picker is the only lead-assignment control on the form and submits
    exactly the checked boxes, so anyone assigned but missing from the list is
    removed by saving any field. eligible_leads() excludes ALUMNI without a
    coach tag and DROPPED members, while the old pill picker applied no status
    filter -- so assignments predating the narrower rule land here.
    """
    lapsed = _untagged_user("Lapsed")
    practice = _practice(4)
    practice_id, lapsed_id = practice.id, lapsed.id
    db.session.add(PracticeLead(practice_id=practice_id, user_id=lapsed_id, role="lead"))
    db_session.commit()

    try:
        rows = {r["user_id"]: r for r in lead_candidates(practice)}
        assert lapsed_id in rows, (
            "an assigned lead must never vanish from the picker -- saving the "
            "form would delete them"
        )
        assert rows[lapsed_id]["in_pool"] is False, \
            "and must be flagged so the picker can say why they're listed"
    finally:
        _cleanup(users=[lapsed_id], practices=[practice_id])


def test_a_non_pool_volunteer_is_surfaced_not_dropped(db_session):
    """The design spec's requirement: reactions from outside the eligible pool
    are recorded AND flagged, so a willing non-tagged member is visible to the
    director rather than silently dropped. Recording already worked; the picker
    iterated the pool, so the offer sat unseen in the database.
    """
    volunteer = _untagged_user("Volunteer")
    practice = _practice(6)
    poll = _open_poll(practice)
    practice_id, poll_id, volunteer_id = practice.id, poll.id, volunteer.id
    _available(poll, practice, volunteer)
    db_session.commit()

    try:
        rows = {r["user_id"]: r for r in lead_candidates(practice)}
        assert volunteer_id in rows, \
            "someone who offered to lead this session must reach the director"
        assert rows[volunteer_id]["available"] is True
        assert rows[volunteer_id]["in_pool"] is False
        # available sorts first, so the volunteer is not buried.
        assert lead_candidates(practice)[0]["user_id"] == volunteer_id
    finally:
        _cleanup(users=[volunteer_id], practices=[practice_id], polls=[poll_id])


def test_pool_members_are_flagged_in_pool(db_session):
    """Positive control for the flag: a normally-tagged lead is in_pool=True,
    so `in_pool` can't pass by being uniformly False.
    """
    lead = _lead_user("Regular")
    practice = _practice(8)
    practice_id, lead_id = practice.id, lead.id
    db_session.commit()

    try:
        rows = {r["user_id"]: r for r in lead_candidates(practice)}
        assert rows[lead_id]["in_pool"] is True
    finally:
        _cleanup(users=[lead_id], practices=[practice_id])


def test_an_outsider_who_neither_answered_nor_is_assigned_stays_out(db_session):
    """The union is scoped: it does not turn the picker into a member list."""
    bystander = _untagged_user("Bystander")
    practice = _practice(10)
    practice_id, bystander_id = practice.id, bystander.id
    db_session.commit()

    try:
        ids = {r["user_id"] for r in lead_candidates(practice)}
        assert bystander_id not in ids
    finally:
        _cleanup(users=[bystander_id], practices=[practice_id])
