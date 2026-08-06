from datetime import datetime, timedelta

import pytest

from app.events.models import (
    Event,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.events.service import (
    RegistrationError,
    capacity_available,
    compute_price,
    create_registration,
    expire_stale_pending,
    questions_for_option,
)


@pytest.fixture
def registration_setup(db_session):
    now = datetime.utcnow()
    event = Event(
        slug="registration-service-test",
        name="Registration Service Test",
        location="Carver Park",
        event_date=now + timedelta(days=30),
        signup_start=now - timedelta(days=1),
        signup_end=now + timedelta(days=1),
        capacity=10,
        status=EventStatus.ACTIVE,
        discount_code=" Club Member ",
        custom_questions=[
            {
                "key": "course",
                "label": "Course",
                "type": "choice",
                "options": ["Long", "Short"],
                "required": True,
                "help_text": "",
            },
            {
                "key": "club",
                "label": "Club",
                "type": "text",
                "options": [],
                "required": False,
                "help_text": "",
            },
        ],
    )
    individual = EventPriceOption(
        name="Individual",
        price_cents=5500,
        member_price_cents=4500,
        participant_roles=["Participant"],
        active=True,
    )
    team = EventPriceOption(
        name="Team of 3",
        price_cents=10500,
        member_price_cents=9000,
        participant_roles=[
            "Rollerskier",
            "Mountain Biker",
            "Trail Runner",
        ],
        active=True,
    )
    event.price_options.extend([individual, team])
    db_session.session.add(event)
    db_session.session.commit()
    return event, individual, team


def _participant(position):
    return {
        "name": f"Participant {position}",
        "date_of_birth": f"199{position}-01-0{position}",
        "email": f"  PERSON{position}@Example.COM ",
        "phone": f"555-010{position}",
        "emergency_contact_name": f" Emergency {position} ",
        "emergency_contact_phone": f"555-099{position}",
    }


def _payload(option, participant_count=None):
    count = (
        option.participant_count
        if participant_count is None
        else participant_count
    )
    return {
        "price_option_id": option.id,
        "team_name": "Nordic Rockets" if count > 1 else None,
        "participants": [
            _participant(position) for position in range(1, count + 1)
        ],
        "answers": {
            "course": "Long",
            "club": "TCSC",
            "unknown": "drop me",
        },
        "discount_code": None,
    }


def _existing_registration(
    db_session,
    event,
    option,
    status,
    created_at,
):
    registration = EventRegistration(
        event_id=event.id,
        price_option_id=option.id,
        contact_email="existing@example.com",
        contact_phone="555-0100",
        answers={},
        amount_cents=option.price_cents,
        status=status,
        created_at=created_at,
    )
    db_session.session.add(registration)
    db_session.session.commit()
    return registration


@pytest.mark.parametrize(
    ("discount_code", "expected"),
    [
        ("  CLUB MEMBER  ", (4500, True)),
        ("wrong", (5500, False)),
        (None, (5500, False)),
    ],
)
def test_compute_price_right_wrong_and_absent_discount_codes(
    registration_setup,
    discount_code,
    expected,
):
    event, individual, _team = registration_setup

    assert compute_price(individual, event, discount_code) == expected


@pytest.mark.parametrize("configured_code", [None, "", "   "])
def test_compute_price_never_matches_an_unset_event_code(
    registration_setup,
    configured_code,
):
    event, individual, _team = registration_setup
    event.discount_code = configured_code

    assert compute_price(individual, event, "") == (5500, False)


def test_compute_price_requires_a_member_price(registration_setup):
    event, individual, _team = registration_setup
    individual.member_price_cents = None

    assert compute_price(individual, event, "club member") == (5500, False)


def test_create_registration_happy_path_individual(
    db_session,
    registration_setup,
):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["discount_code"] = "club MEMBER"

    registration = create_registration(event, payload)
    registration_id = registration.id
    db_session.session.expire_all()
    saved = db_session.session.get(EventRegistration, registration_id)

    assert saved.status == RegistrationStatus.PENDING_PAYMENT
    assert saved.amount_cents == 4500
    assert saved.discount_applied is True
    assert saved.contact_email == "person1@example.com"
    assert saved.contact_phone == "555-0101"
    assert saved.team_name is None
    assert saved.answers == {"course": "Long", "club": "TCSC"}
    assert len(saved.participants) == 1
    assert saved.participants[0].position == 1
    assert saved.participants[0].role_label == "Participant"
    assert saved.participants[0].email == "person1@example.com"
    assert saved.participants[0].date_of_birth.isoformat() == "1991-01-01"


def test_create_registration_happy_path_team_copies_roles(
    registration_setup,
):
    event, _individual, team = registration_setup

    registration = create_registration(event, _payload(team))

    assert registration.team_name == "Nordic Rockets"
    assert [participant.position for participant in registration.participants] == [
        1,
        2,
        3,
    ]
    assert [
        participant.role_label for participant in registration.participants
    ] == [
        "Rollerskier",
        "Mountain Biker",
        "Trail Runner",
    ]


def test_create_registration_rejects_wrong_participant_count(
    registration_setup,
):
    event, _individual, team = registration_setup

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(team, participant_count=2))

    assert "participants" in exc_info.value.errors


def test_team_name_is_required_for_teams_only(registration_setup):
    event, individual, team = registration_setup
    team_payload = _payload(team)
    team_payload["team_name"] = " "

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, team_payload)

    assert "team_name" in exc_info.value.errors

    individual_payload = _payload(individual)
    individual_payload["team_name"] = None
    registration = create_registration(event, individual_payload)
    assert registration.team_name is None


def test_create_registration_rejects_missing_required_question(
    registration_setup,
):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["answers"]["course"] = " "

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "answers.course" in exc_info.value.errors


def test_create_registration_rejects_invalid_choice(registration_setup):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["answers"]["course"] = "Medium"

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "answers.course" in exc_info.value.errors


def test_create_registration_collects_required_field_errors(
    registration_setup,
):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["participants"][0]["name"] = ""
    payload["participants"][0]["email"] = " "

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "participants" in exc_info.value.errors


def test_each_participant_requires_emergency_contact(registration_setup):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    del payload["participants"][0]["emergency_contact_name"]
    payload["participants"][0]["emergency_contact_phone"] = "  "

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    message = exc_info.value.errors["participants"]
    assert "Participant 1 requires" in message
    assert "emergency contact name" in message
    assert "emergency contact phone" in message


def test_participants_store_their_own_emergency_contact(registration_setup):
    event, _individual, team = registration_setup

    registration = create_registration(event, _payload(team))

    for position, participant in enumerate(
        registration.participants, start=1
    ):
        assert participant.emergency_contact_name == f"Emergency {position}"
        assert participant.emergency_contact_phone == f"555-099{position}"


def test_registration_level_emergency_contact_is_ignored(registration_setup):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["emergency_contact_name"] = "Legacy Top Level"
    payload["emergency_contact_phone"] = "555-0000"

    registration = create_registration(event, payload)

    assert not hasattr(registration, "emergency_contact_name")


def test_create_registration_rejects_unparseable_participant_dob(
    registration_setup,
):
    event, individual, _team = registration_setup
    payload = _payload(individual)
    payload["participants"][0]["date_of_birth"] = "January 1"

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "participants" in exc_info.value.errors


def test_create_registration_rejects_inactive_option(registration_setup):
    event, individual, _team = registration_setup
    individual.active = False

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(individual))

    assert "price_option_id" in exc_info.value.errors


def test_create_registration_rejects_option_from_another_event(
    db_session,
    registration_setup,
):
    event, _individual, _team = registration_setup
    other_event = Event(
        slug="registration-service-other",
        name="Other Event",
        location="Other Location",
        event_date=event.event_date,
        signup_start=event.signup_start,
        signup_end=event.signup_end,
        status=EventStatus.ACTIVE,
    )
    other_option = EventPriceOption(
        name="Other Option",
        price_cents=1000,
        participant_roles=["Participant"],
    )
    other_event.price_options.append(other_option)
    db_session.session.add(other_event)
    db_session.session.commit()

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(other_option))

    assert "price_option_id" in exc_info.value.errors


def test_create_registration_rejects_confirmed_capacity_full(
    db_session,
    registration_setup,
):
    event, individual, _team = registration_setup
    event.capacity = 1
    _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.CONFIRMED,
        datetime.utcnow() - timedelta(days=30),
    )

    assert capacity_available(event) is False
    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(individual))

    assert "capacity" in exc_info.value.errors


def test_recent_pending_holds_capacity_but_one_over_an_hour_old_does_not(
    db_session,
    registration_setup,
):
    event, individual, _team = registration_setup
    event.capacity = 1
    pending = _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.PENDING_PAYMENT,
        datetime.utcnow() - timedelta(minutes=59),
    )

    assert capacity_available(event) is False

    pending.created_at = datetime.utcnow() - timedelta(hours=1, seconds=1)
    db_session.session.commit()

    assert capacity_available(event) is True


def test_unlimited_event_always_has_capacity(
    db_session,
    registration_setup,
):
    event, individual, _team = registration_setup
    event.capacity = None
    _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.CONFIRMED,
        datetime.utcnow(),
    )

    assert capacity_available(event) is True


def test_expire_stale_pending_cancels_only_rows_older_than_24_hours(
    db_session,
    registration_setup,
):
    event, individual, _team = registration_setup
    stale = _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.PENDING_PAYMENT,
        datetime.utcnow() - timedelta(hours=24, seconds=1),
    )
    recent = _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.PENDING_PAYMENT,
        datetime.utcnow() - timedelta(hours=23, minutes=59),
    )
    confirmed = _existing_registration(
        db_session,
        event,
        individual,
        RegistrationStatus.CONFIRMED,
        datetime.utcnow() - timedelta(days=2),
    )
    ids = [stale.id, recent.id, confirmed.id]

    assert expire_stale_pending(event) == 1

    db_session.session.expire_all()
    statuses = [
        db_session.session.get(EventRegistration, registration_id).status
        for registration_id in ids
    ]
    assert statuses == [
        RegistrationStatus.CANCELLED,
        RegistrationStatus.PENDING_PAYMENT,
        RegistrationStatus.CONFIRMED,
    ]


def test_draft_event_rejected_unless_explicitly_allowed(
    registration_setup,
):
    event, individual, _team = registration_setup
    event.status = EventStatus.DRAFT

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(individual))

    assert "event" in exc_info.value.errors

    registration = create_registration(
        event,
        _payload(individual),
        allow_draft=True,
    )
    assert registration.status == RegistrationStatus.PENDING_PAYMENT


@pytest.mark.parametrize("window", ["not_started", "ended"])
def test_create_registration_rejects_closed_signup_window(
    registration_setup,
    window,
):
    event, individual, _team = registration_setup
    now = datetime.utcnow()
    if window == "not_started":
        event.signup_start = now + timedelta(hours=1)
    else:
        event.signup_end = now - timedelta(hours=1)

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, _payload(individual))

    assert "event" in exc_info.value.errors


def test_contact_details_come_from_the_first_participant(
    db_session,
    registration_setup,
):
    event, _individual, team = registration_setup
    payload = _payload(team)
    payload["contact_email"] = "spoofed@example.com"
    payload["contact_phone"] = "555-9999"

    registration = create_registration(event, payload)
    registration_id = registration.id
    db_session.session.expire_all()
    saved = db_session.session.get(EventRegistration, registration_id)

    assert saved.contact_email == "person1@example.com"
    assert saved.contact_phone == "555-0101"
    assert saved.participants[0].email == "person1@example.com"


def test_question_scoped_to_other_options_is_neither_required_nor_stored(
    registration_setup,
):
    event, individual, team = registration_setup
    event.custom_questions = [
        {
            "key": "course",
            "label": "Course",
            "type": "choice",
            "options": ["Long", "Short"],
            "required": True,
            "price_options": ["Team of 3"],
        },
    ]
    payload = _payload(individual)
    payload["answers"] = {"course": "Long"}

    registration = create_registration(event, payload)

    assert registration.answers == {}
    assert questions_for_option(event, individual) == []
    assert len(questions_for_option(event, team)) == 1


def test_unscoped_question_applies_to_every_option(registration_setup):
    event, individual, team = registration_setup
    event.custom_questions = [
        {
            "key": "club",
            "label": "Club",
            "type": "text",
            "required": True,
        },
    ]

    for option in (individual, team):
        assert len(questions_for_option(event, option)) == 1

    payload = _payload(individual)
    payload["answers"] = {}

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "answers.club" in exc_info.value.errors


def test_scope_naming_no_surviving_option_falls_open_to_applying(
    registration_setup,
):
    event, individual, _team = registration_setup
    event.custom_questions = [
        {
            "key": "club",
            "label": "Club",
            "type": "text",
            "required": True,
            "price_options": ["Renamed Away"],
        },
    ]

    assert len(questions_for_option(event, individual)) == 1


def test_scope_is_honoured_when_any_named_option_still_exists(
    registration_setup,
):
    event, individual, team = registration_setup
    event.custom_questions = [
        {
            "key": "club",
            "label": "Club",
            "type": "text",
            "required": True,
            "price_options": ["Team of 3", "Renamed Away"],
        },
    ]

    assert questions_for_option(event, individual) == []
    assert len(questions_for_option(event, team)) == 1


def test_disjoint_scoped_duplicate_keys_ask_one_question_per_option(
    registration_setup,
):
    event, individual, team = registration_setup
    event.custom_questions = [
        {
            "key": "competition_gender",
            "label": "Competition gender",
            "type": "choice",
            "options": ["Men", "Women", "Non-binary"],
            "required": True,
            "price_options": ["Individual"],
        },
        {
            "key": "competition_gender",
            "label": "Competition gender",
            "type": "choice",
            "options": ["Men", "Women", "Mixed"],
            "required": True,
            "price_options": ["Team of 3"],
        },
    ]

    individual_questions = questions_for_option(event, individual)
    team_questions = questions_for_option(event, team)

    assert [question["options"] for question in individual_questions] == [
        ["Men", "Women", "Non-binary"]
    ]
    assert [question["options"] for question in team_questions] == [
        ["Men", "Women", "Mixed"]
    ]

    payload = _payload(team)
    payload["answers"] = {"competition_gender": "Mixed"}
    registration = create_registration(event, payload)

    assert registration.answers == {"competition_gender": "Mixed"}


def test_individual_option_rejects_the_team_only_gender_answer(
    registration_setup,
):
    event, individual, _team = registration_setup
    event.custom_questions = [
        {
            "key": "competition_gender",
            "label": "Competition gender",
            "type": "choice",
            "options": ["Men", "Women", "Non-binary"],
            "required": True,
            "price_options": ["Individual"],
        },
        {
            "key": "competition_gender",
            "label": "Competition gender",
            "type": "choice",
            "options": ["Men", "Women", "Mixed"],
            "required": True,
            "price_options": ["Team of 3"],
        },
    ]
    payload = _payload(individual)
    payload["answers"] = {"competition_gender": "Mixed"}

    with pytest.raises(RegistrationError) as exc_info:
        create_registration(event, payload)

    assert "answers.competition_gender" in exc_info.value.errors
