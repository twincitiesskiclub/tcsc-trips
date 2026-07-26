"""Publishing drafts — the step that makes a practice member-visible.

`generate_draft_block()` creates practices with `is_draft=True` so coaches can
fill in location, type and time and collect lead availability against real
details without members seeing a half-built schedule. This module is the other
end of that: flipping `is_draft` back to False is the *only* thing standing
between a fully-staffed practice and every member-facing surface, all of which
read through `published_practices()`.

Publishing deliberately does not post the announcement itself. The
announcement job already scans `published_practices()` for rows with no
`slack_message_ts` and posts them on the configured schedule, so flipping the
flag hands the practice to the existing pipeline rather than duplicating its
timing rules here. What this module does fan out is
`refresh_practice_posts(change_type='create')`, which brings the coach and
weekly summaries in line — the same call `create_practice()` makes.
"""

from flask import current_app

from app.models import db
from app.practices.drafting import missing_fields
from app.practices.interfaces import PracticeStatus

# Rendered into the same "what's missing" list as the drafting fields, so both
# the batch report and the UI that displays it need no special case for it.
_CANCELLED_BLOCKER = "not cancelled"


def publish_blockers(practice) -> list[str]:
    """Everything standing between this draft and members seeing it.

    Public because every surface that offers a Publish button has to count
    "ready" the same way this module does -- a grid banner or Slack button that
    promises to publish N practices and then skips one has simply lied.

    Location/type/time come from drafting.missing_fields(), the shared gate
    build_poll() uses -- a practice that can be polled against can be
    published. Cancellation is added here: build_poll() excludes CANCELLED
    practices outright, so publishing has to agree, or a cancelled draft caught
    in a week-wide batch reaches members as a real session.
    """
    blockers = missing_fields(practice)
    if practice.status == PracticeStatus.CANCELLED.value:
        blockers.append(_CANCELLED_BLOCKER)
    return blockers


class NotReadyToPublishError(RuntimeError):
    """Raised when a draft still lacks the details members would need.

    Mirrors `PollNotReadyError` from app/practices/availability.py, and on
    purpose: both gate on `missing_fields()`, so a practice that can be polled
    can also be published. The message names the practice and the missing
    fields, because whoever clicked Publish is the person who has to go fix it.
    """


def _fan_out(practice, actor_slack_id=None):
    """Best-effort Slack refresh for a practice that is already committed.

    Never raises. The `is_draft` flip is committed before this runs, so a
    Slack outage must not roll back publication — leaving the practice
    invisible to members would silently undo the one thing the director asked
    for. Failures are logged loudly instead, and the announcement job will
    still pick the practice up on its next pass regardless.
    """
    try:
        from app.slack.practices.refresh import refresh_practice_posts

        results = refresh_practice_posts(
            practice,
            change_type="create",
            actor_slack_id=actor_slack_id,
        )
        for surface, result in (results or {}).items():
            if isinstance(result, dict) and result.get("success") is False:
                current_app.logger.warning(
                    "Practice #%s was published but %s refresh failed: %s",
                    practice.id,
                    surface,
                    result.get("error", "unknown error"),
                )
        return results
    except Exception:  # noqa: BLE001 - see docstring; publication already stands
        current_app.logger.exception(
            "Practice #%s was published but the Slack refresh raised",
            practice.id,
        )
        return None


def publish_practice(practice, *, actor_slack_id=None):
    """Make one draft visible to members, or refuse and say why.

    Raises rather than reporting, unlike `publish_practices()`: a single
    Publish click names one specific practice, so silently doing nothing would
    look like the button is broken.
    """
    if not practice.is_draft:
        return {
            "success": True,
            "already_published": True,
            "practice_id": practice.id,
        }

    missing = publish_blockers(practice)
    if missing:
        raise NotReadyToPublishError(
            f"{practice.date:%a %-m/%-d} still needs {', '.join(missing)} "
            "before it can be published"
        )

    practice.is_draft = False
    db.session.commit()
    current_app.logger.info(
        "Published practice #%s (%s)", practice.id, practice.date
    )

    _fan_out(practice, actor_slack_id)
    return {"success": True, "practice_id": practice.id}


def publish_practices(practices, *, actor_slack_id=None):
    """Publish every ready draft in a batch and report on the rest.

    Reports instead of raising because this backs the Sunday batch — the grid
    selection and the weekly Slack post both hand over a whole week at once,
    routinely including rows that are already live or still missing details.
    Aborting on the first incomplete draft would put the director back to one
    click per fix, which is how a tool like this gets abandoned.

    All the flag flips share one commit, so a batch is atomic in the database;
    the Slack fan-out then runs per practice and is individually best-effort.
    """
    ready = []
    skipped = []
    already_published = []

    for practice in practices:
        if not practice.is_draft:
            already_published.append(practice.id)
            continue
        missing = publish_blockers(practice)
        if missing:
            skipped.append({"practice_id": practice.id, "missing": missing})
            continue
        practice.is_draft = False
        ready.append(practice)

    if ready:
        db.session.commit()
        current_app.logger.info(
            "Published %d practice(s): %s",
            len(ready),
            ", ".join(str(p.id) for p in ready),
        )
        for practice in ready:
            _fan_out(practice, actor_slack_id)

    return {
        "success": True,
        "published": [p.id for p in ready],
        "skipped": skipped,
        "already_published": already_published,
    }
