"""Business logic for event registration, pricing, and capacity."""

from datetime import datetime, timedelta

from sqlalchemy import and_, or_

from app.events.models import (
    Event,
    EventParticipant,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.models import db
from app.utils import normalize_email, parse_date


class RegistrationError(Exception):
    """Field-level event registration validation errors."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("Event registration validation failed")


def discount_code_matches(event: Event, discount_code: str | None) -> bool:
    """Return whether ``discount_code`` is the event's configured code."""
    configured_code = (
        event.discount_code.strip().casefold()
        if isinstance(event.discount_code, str)
        else ""
    )
    submitted_code = (
        discount_code.strip().casefold()
        if isinstance(discount_code, str)
        else ""
    )
    return bool(configured_code) and configured_code == submitted_code


def compute_price(
    option: EventPriceOption,
    event: Event,
    discount_code: str | None,
) -> tuple[int, bool]:
    """Return the server-computed price and whether a discount was applied."""
    if (
        discount_code_matches(event, discount_code)
        and option.member_price_cents is not None
    ):
        return option.member_price_cents, True
    return option.price_cents, False


def questions_for_option(
    event: Event,
    option: EventPriceOption | None,
) -> list[dict]:
    """Return the event's custom questions that apply to ``option``."""
    questions = [
        question
        for question in (event.custom_questions or [])
        if isinstance(question, dict)
    ]
    if option is None:
        return questions

    known_names = {existing.name for existing in event.price_options}
    return [
        question
        for question in questions
        if _question_in_scope(question, option, known_names)
    ]


def _question_in_scope(
    question: dict,
    option: EventPriceOption,
    known_names: set[str],
) -> bool:
    scope = question.get("price_options")
    names = (
        [name for name in scope if isinstance(name, str)]
        if isinstance(scope, list)
        else []
    )
    if not names:
        return True
    if option.name in names:
        return True
    # A scope naming no surviving price option falls open to applying, so
    # renaming an option cannot silently drop a required question.
    return not any(name in known_names for name in names)


def capacity_available(event: Event) -> bool:
    """Return whether the event has room for another registration."""
    if event.capacity is None:
        return True

    pending_cutoff = datetime.utcnow() - timedelta(hours=1)
    held_spots = EventRegistration.query.filter(
        EventRegistration.event_id == event.id,
        or_(
            EventRegistration.status == RegistrationStatus.CONFIRMED,
            and_(
                EventRegistration.status
                == RegistrationStatus.PENDING_PAYMENT,
                EventRegistration.created_at > pending_cutoff,
            ),
        ),
    ).count()
    return held_spots < event.capacity


def expire_stale_pending(event: Event) -> int:
    """Cancel pending registrations older than 24 hours and commit."""
    stale_cutoff = datetime.utcnow() - timedelta(hours=24)
    stale_registrations = EventRegistration.query.filter(
        EventRegistration.event_id == event.id,
        EventRegistration.status == RegistrationStatus.PENDING_PAYMENT,
        EventRegistration.created_at < stale_cutoff,
    ).all()

    for registration in stale_registrations:
        registration.status = RegistrationStatus.CANCELLED

    db.session.commit()
    return len(stale_registrations)


def create_registration(
    event: Event,
    payload: dict,
    *,
    allow_draft: bool = False,
) -> EventRegistration:
    """Validate, create, and commit a pending event registration."""
    errors: dict[str, str] = {}
    now = datetime.utcnow()

    event_is_open = event.status == EventStatus.ACTIVE or (
        allow_draft and event.status == EventStatus.DRAFT
    )
    if not event_is_open:
        errors["event"] = "Registration is not open for this event."

    if now < event.signup_start or now > event.signup_end:
        errors["event"] = "Registration is outside the signup window."

    option = _get_valid_option(event, payload.get("price_option_id"))
    if option is None:
        errors["price_option_id"] = (
            "Select an active price option for this event."
        )

    participants = payload.get("participants")
    if not isinstance(participants, list):
        errors["participants"] = "Participants must be provided as a list."
        participants = []

    if option is not None and len(participants) != option.participant_count:
        errors["participants"] = (
            f"This option requires {option.participant_count} participant(s)."
        )

    validated_participants, participant_errors = _validate_participants(
        participants
    )
    if participant_errors:
        errors["participants"] = "; ".join(participant_errors)

    team_name = payload.get("team_name")
    if option is not None and option.participant_count > 1:
        if _is_blank(team_name):
            errors["team_name"] = "Team name is required for team options."

    stored_answers, answer_errors = _validate_answers(
        questions_for_option(event, option),
        payload.get("answers"),
    )
    errors.update(answer_errors)

    if not capacity_available(event):
        errors["capacity"] = "This event is at capacity."

    if errors:
        raise RegistrationError(errors)

    amount_cents, discount_applied = compute_price(
        option,
        event,
        payload.get("discount_code"),
    )
    # Participant details are the only contact we collect; the first
    # participant is who Stripe emails and who the roster lists.
    primary_participant = validated_participants[0]
    registration = EventRegistration(
        event_id=event.id,
        price_option_id=option.id,
        contact_email=primary_participant["email"],
        contact_phone=primary_participant["phone"],
        team_name=_optional_text(team_name),
        answers=stored_answers,
        amount_cents=amount_cents,
        discount_applied=discount_applied,
        status=RegistrationStatus.PENDING_PAYMENT,
    )

    roles = option.participant_roles or ["Participant"]
    for position, participant in enumerate(validated_participants, start=1):
        registration.participants.append(
            EventParticipant(
                position=position,
                role_label=roles[position - 1],
                name=participant["name"],
                date_of_birth=participant["date_of_birth"],
                email=participant["email"],
                phone=participant["phone"],
                emergency_contact_name=participant["emergency_contact_name"],
                emergency_contact_phone=participant[
                    "emergency_contact_phone"
                ],
            )
        )

    db.session.add(registration)
    db.session.commit()
    return registration


def _get_valid_option(
    event: Event,
    option_id,
) -> EventPriceOption | None:
    if (
        not isinstance(option_id, int)
        or isinstance(option_id, bool)
        or option_id < 1
    ):
        return None

    option = db.session.get(EventPriceOption, option_id)
    if option is None or option.event_id != event.id or not option.active:
        return None
    return option


def _validate_participants(
    participants: list,
) -> tuple[list[dict], list[str]]:
    validated = []
    errors = []

    for index, participant in enumerate(participants, start=1):
        if not isinstance(participant, dict):
            errors.append(f"Participant {index} must be an object.")
            continue

        missing_fields = [
            field
            for field in (
                "name",
                "date_of_birth",
                "email",
                "phone",
                "emergency_contact_name",
                "emergency_contact_phone",
            )
            if _is_blank(participant.get(field))
        ]
        if missing_fields:
            errors.append(
                f"Participant {index} requires: "
                + ", ".join(field.replace("_", " ") for field in missing_fields)
                + "."
            )

        date_of_birth = None
        raw_date_of_birth = participant.get("date_of_birth")
        if not _is_blank(raw_date_of_birth):
            try:
                date_of_birth = parse_date(raw_date_of_birth)
            except (TypeError, ValueError):
                errors.append(
                    f"Participant {index} has an invalid date of birth."
                )

        email = _normalized_email(participant.get("email"))
        if missing_fields or date_of_birth is None or not email:
            continue

        validated.append(
            {
                "name": participant["name"].strip(),
                "date_of_birth": date_of_birth,
                "email": email,
                "phone": participant["phone"].strip(),
                "emergency_contact_name": participant[
                    "emergency_contact_name"
                ].strip(),
                "emergency_contact_phone": participant[
                    "emergency_contact_phone"
                ].strip(),
            }
        )

    return validated, errors


def _validate_answers(
    questions: list[dict],
    submitted_answers,
) -> tuple[dict[str, str], dict[str, str]]:
    errors = {}
    if submitted_answers is None:
        submitted_answers = {}
    elif not isinstance(submitted_answers, dict):
        return {}, {"answers": "Answers must be provided as an object."}

    stored_answers = {}
    for question in questions:
        key = question.get("key")
        if not key:
            continue

        supplied = key in submitted_answers
        answer = submitted_answers.get(key)
        answered = not _is_blank(answer)
        error_key = f"answers.{key}"
        label = question.get("label") or key

        if question.get("required") and not answered:
            errors[error_key] = f"{label} is required."
        elif (
            answered
            and question.get("type") == "choice"
            and answer not in (question.get("options") or [])
        ):
            errors[error_key] = f"Select a valid option for {label}."

        if supplied:
            stored_answers[key] = answer

    return stored_answers, errors


def _normalized_email(value) -> str:
    if not isinstance(value, str):
        return ""
    return normalize_email(value)


def _is_blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _optional_text(value) -> str | None:
    if _is_blank(value):
        return None
    return value.strip()
