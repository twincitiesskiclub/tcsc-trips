"""Rank the eligible lead pool for one practice.

Assignment is a human judgment call, so nobody is ever filtered out -- this
sorts and labels only. Unavailable and never-responded candidates sort last,
but every eligible lead/coach is always present in the returned list.
"""

from datetime import timedelta

from app.practices.availability import eligible_leads
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice, PracticeLead

LOAD_WINDOW_DAYS = 90

# Participant statuses that mean "we heard from this person" (as opposed to
# PENDING, which just means they were asked and haven't answered yet).
_RESPONDED_STATUSES = (ParticipantStatus.RESPONDED, ParticipantStatus.DONE, ParticipantStatus.OPTED_OUT)


def _poll_for_practice(practice: Practice) -> LeadAvailabilityPoll | None:
    """The most recent poll that included this practice, if any."""
    return (
        LeadAvailabilityPoll.query
        .join(LeadAvailabilityPollPractice,
              LeadAvailabilityPollPractice.poll_id == LeadAvailabilityPoll.id)
        .filter(LeadAvailabilityPollPractice.practice_id == practice.id,
                LeadAvailabilityPoll.status.in_([PollStatus.OPEN, PollStatus.CLOSED]))
        .order_by(LeadAvailabilityPoll.created_at.desc())
        .first()
    )


def _is_stale(response: LeadAvailabilityResponse, practice: Practice) -> bool:
    """Did the details that decide availability change after they answered?

    Deliberately compares against the response's own snapshot
    (answered_for_date / answered_for_location_id), never against
    Practice.updated_at -- that column has onupdate and fires on any edit, so
    a workout-text tweak would mark every response stale and the warning
    would stop meaning anything within a week.
    """
    if response.answered_for_date != practice.date:
        return True
    if response.answered_for_location_id != practice.location_id:
        return True
    return False


def _load_counts(user_ids: list[int], poll: LeadAvailabilityPoll | None, anchor) -> tuple[dict, dict]:
    """Leads led within the poll's block, and in the 90 days before `anchor`.

    Only role='lead' counts -- the assist role is retired and must not add
    load. The trailing window is anchored to the practice being scheduled,
    not to whatever the newest matching row happens to be: anchoring to the
    data would make the number drift every time anyone anywhere leads a
    practice.
    """
    in_block = {uid: 0 for uid in user_ids}
    recent = {uid: 0 for uid in user_ids}
    if not user_ids:
        return in_block, recent

    window_start = anchor - timedelta(days=LOAD_WINDOW_DAYS)

    rows = (
        PracticeLead.query
        .join(Practice, Practice.id == PracticeLead.practice_id)
        .filter(PracticeLead.user_id.in_(user_ids), PracticeLead.role == "lead")
        .with_entities(PracticeLead.user_id, Practice.date)
        .all()
    )

    for user_id, when in rows:
        if poll is not None and poll.starts_on <= when.date() <= poll.ends_on:
            in_block[user_id] += 1
        if window_start <= when <= anchor:
            recent[user_id] += 1

    return in_block, recent


def lead_candidates(practice: Practice) -> list[dict]:
    """The eligible pool for `practice`, ranked for the director to pick from.

    Ordering: available first, then fewest led_in_block, then fewest
    led_last_90d, then name. Unavailable and no-response candidates are never
    removed -- they simply sort last.
    """
    poll = _poll_for_practice(practice)
    users = eligible_leads()
    user_ids = [u.id for u in users]

    responses: dict[int, LeadAvailabilityResponse] = {}
    responded: set[int] = set()
    if poll is not None:
        responses = {
            r.user_id: r for r in LeadAvailabilityResponse.query.filter_by(
                poll_id=poll.id, practice_id=practice.id).all()
        }
        responded = {
            p.user_id for p in LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
            if p.status in _RESPONDED_STATUSES
        }

    in_block, recent = _load_counts(user_ids, poll, practice.date)

    rows = []
    for user in users:
        response = responses.get(user.id)
        rows.append({
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "available": response is not None,
            "responded": user.id in responded or response is not None,
            "stale": response is not None and _is_stale(response, practice),
            "led_in_block": in_block.get(user.id, 0),
            "led_last_90d": recent.get(user.id, 0),
        })

    rows.sort(key=lambda r: (
        not r["available"],   # available first
        r["led_in_block"],    # then fewest led this block
        r["led_last_90d"],    # then fewest led in the last 90 days
        r["name"],
    ))
    return rows
