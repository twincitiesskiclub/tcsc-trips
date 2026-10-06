"""Trip registration domain logic. Parallel to app/events/service.py.

Unpaid attempts reuse the member's registration row and restart its capacity
hold. Only PENDING and CONFIRMED registrations block another attempt. Rows
are committed PENDING_PAYMENT before Stripe; the route reconciles any previous
intent before creating a new manual-capture hold. Capacity ignores unpaid
attempts after 1h, and a 24h sweep cancels abandoned rows.
"""
from datetime import datetime, timedelta

from app.constants import UserStatus
from app.models import db, User
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus
from app.utils import normalize_email

PENDING_HOLD_WINDOW = timedelta(hours=1)
STALE_PENDING_AGE = timedelta(hours=24)

HITCH_SIZES = {"", "1.25", "2"}


class TripRegistrationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))


def lookup_active_member(email):
    user = User.get_by_email(normalize_email(email))
    if user and user.status == UserStatus.ACTIVE:
        return user
    return None


def visible_questions(questions, answers):
    """Which questions apply given the submitted answers. Mirrored client-side
    in trip_registration.js (applyVisibility) - keep the two in sync."""
    visible = []
    for question in questions or []:
        condition = question.get("visible_if")
        if condition:
            if answers.get(condition["question"]) != condition["equals"]:
                continue
        visible.append(question)
    return visible


def validate_answers(questions, submitted):
    if not isinstance(submitted, dict):
        return {}, {"answers": "Answers must be provided as an object."}
    stored, errors = {}, {}
    for question in visible_questions(questions, submitted):
        if "builtin" in question:
            continue
        key = question["key"]
        label = question.get("label") or key
        answer = submitted.get(key)
        qtype = question["type"]
        if qtype == "multi_choice":
            if answer is None:
                answer = []
            if not isinstance(answer, list):
                errors[f"answers.{key}"] = f"{label} must be a list."
                continue
            answer = [str(a) for a in answer]
            if question.get("required") and not answer:
                errors[f"answers.{key}"] = f"{label} is required."
                continue
            invalid = [a for a in answer if a not in question["options"]]
            if invalid:
                errors[f"answers.{key}"] = f"Select valid options for {label}."
                continue
            cap = question.get("max_selections")
            if cap and len(answer) > cap:
                errors[f"answers.{key}"] = (
                    f"Pick at most {cap} options for {label}.")
                continue
            if answer:
                stored[key] = answer
            continue
        answer = "" if answer is None else str(answer).strip()
        if question.get("required") and not answer:
            errors[f"answers.{key}"] = f"{label} is required."
            continue
        if answer and qtype == "choice" and answer not in question["options"]:
            errors[f"answers.{key}"] = f"Select a valid option for {label}."
            continue
        if answer and qtype == "yes_no" and answer not in ("yes", "no"):
            errors[f"answers.{key}"] = f"Answer yes or no for {label}."
            continue
        if answer:
            stored[key] = answer
    return stored, errors


def _parse_optional_int(value, field, errors, *, maximum=99):
    if value in (None, ""):
        return None
    if isinstance(value, bool):  # bool is an int subclass; True would store 1
        errors[field] = "Enter a whole number."
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = "Enter a whole number."
        return None
    if number < 0 or number > maximum:
        errors[field] = f"Enter a number between 0 and {maximum}."
        return None
    return number


def _parse_yes_no(value):
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def validate_profile(questions, payload):
    """Validate only enabled built-ins, using their fixed profile mapping.

    Omitted columns must stay omitted so upsert preserves earlier answers.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return {}, {"profile": "Profile must be provided as an object."}
    clean, errors = {}, {}
    for question in questions or []:
        builtin = question.get("builtin")
        if not builtin or not question["enabled"]:
            continue
        required = question["required"]
        if builtin in ("carpool", "tent"):
            field = "can_drive" if builtin == "carpool" else "has_tent"
            answer = payload.get(field)
            if answer not in ("yes", "no") and (required or answer not in (None, "")):
                errors[f"profile.{field}"] = f"Answer yes or no for {question['label']}"
            clean[field] = _parse_yes_no(answer)
        if builtin == "carpool":
            # Driver details apply only to a yes answer, just like the reveal.
            driving = clean["can_drive"] is True
            followups = question["followups"]
            for key, field in (("seats", "seat_capacity"), ("bikes", "bike_capacity")):
                if followups[key]["enabled"]:
                    clean[field] = _parse_optional_int(
                        payload.get(field) if driving else None, f"profile.{field}", errors)
            if followups["hitch"]["enabled"]:
                hitch = str(payload.get("hitch_size") or "") if driving else ""
                if hitch not in HITCH_SIZES:
                    errors["profile.hitch_size"] = "Choose a valid hitch size."
                clean["hitch_size"] = hitch
        elif builtin == "region_code":
            region = str(payload.get("region_code") or "").strip()
            if required and not region:
                errors["profile.region_code"] = "Your region code is required."
            elif len(region) > 10:
                errors["profile.region_code"] = "Region code is too long."
            clean["region_code"] = region
        elif builtin == "dietary":
            dietary = payload.get("dietary_restrictions", [])
            if dietary is None:
                dietary = []
            if not isinstance(dietary, list):
                errors["profile.dietary_restrictions"] = "Dietary picks must be a list."
                dietary = []
            elif any(d not in question["options"] for d in dietary):
                errors["profile.dietary_restrictions"] = "Choose valid dietary options."
            elif required and not dietary:
                errors["profile.dietary_restrictions"] = "Select at least one dietary option."
            clean["dietary_restrictions"] = dietary
            clean["dietary_other"] = str(payload.get("dietary_other") or "").strip()[:255]
    return clean, errors


def upsert_profile(user, clean_profile):
    profile = TripProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        profile = TripProfile(user_id=user.id)
        db.session.add(profile)
    for field, value in clean_profile.items():
        setattr(profile, field, value)
    return profile


def _active_count(trip, *, exclude_registration_id=None):
    recent_cutoff = datetime.utcnow() - PENDING_HOLD_WINDOW
    count = 0
    for registration in trip.registrations:
        if registration.id == exclude_registration_id:
            continue
        if registration.status in (TripRegistrationStatus.PENDING,
                                   TripRegistrationStatus.CONFIRMED):
            count += 1
        elif (registration.status == TripRegistrationStatus.PENDING_PAYMENT
              and registration.created_at >= recent_cutoff):
            count += 1
    return count


def capacity_available(trip, *, exclude_registration_id=None):
    capacity = (trip.max_participants_standard or 0) + (
        trip.max_participants_extra or 0)
    if capacity <= 0:
        return True
    return _active_count(trip, exclude_registration_id=exclude_registration_id) < capacity


def expire_stale_pending(trip):
    cutoff = datetime.utcnow() - STALE_PENDING_AGE
    stale = TripRegistration.query.filter(
        TripRegistration.trip_id == trip.id,
        TripRegistration.status == TripRegistrationStatus.PENDING_PAYMENT,
        TripRegistration.created_at < cutoff,
    ).all()
    if not stale:
        return
    for registration in stale:
        registration.status = TripRegistrationStatus.CANCELLED
    db.session.commit()


def create_registration(trip, payload):
    """Return the unpaid registration and any intent the route must reconcile."""
    if not isinstance(payload, dict):
        raise TripRegistrationError(
            {"payload": "Registration data must be an object."})
    errors = {}
    now = datetime.utcnow()
    if trip.status != "active" or not (
            trip.signup_start <= now <= trip.signup_end):
        raise TripRegistrationError(
            {"trip": "Trip registration is not currently open."})

    user = lookup_active_member(payload.get("email") or "")
    if user is None:
        raise TripRegistrationError({
            "email": "We couldn't find a current member with that email. "
                     "Trips are open to registered members only."})

    existing = TripRegistration.query.filter(
        TripRegistration.trip_id == trip.id,
        TripRegistration.user_id == user.id,
    ).first()
    if existing and existing.status in (
            TripRegistrationStatus.PENDING, TripRegistrationStatus.CONFIRMED):
        raise TripRegistrationError(
            {"email": "You're already signed up for this trip."})

    price_tier = payload.get("price_tier")
    if price_tier == "low":
        amount_cents = trip.price_low
    elif price_tier == "high":
        amount_cents = trip.price_high
    else:
        errors["price_tier"] = "Choose a valid price option."

    clean_profile, profile_errors = validate_profile(
        trip.custom_questions, payload.get("profile"))
    errors.update(profile_errors)
    stored_answers, answer_errors = validate_answers(
        trip.custom_questions or [], payload.get("answers") or {})
    errors.update(answer_errors)
    if errors:
        raise TripRegistrationError(errors)

    if not capacity_available(trip, exclude_registration_id=existing.id if existing else None):
        raise TripRegistrationError(
            {"trip": "This trip is full."})

    upsert_profile(user, clean_profile)
    registration = existing or TripRegistration(trip_id=trip.id, user_id=user.id)
    previous_intent_id = registration.payment_intent_id
    registration.status = TripRegistrationStatus.PENDING_PAYMENT
    registration.answers = stored_answers
    registration.price_tier = price_tier
    registration.amount_cents = amount_cents
    registration.created_at = now
    registration.payment_intent_id = None
    db.session.add(registration)
    db.session.commit()
    return registration, previous_intent_id
