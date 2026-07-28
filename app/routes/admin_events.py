"""Admin CRUD, roster, and export routes for generic events."""

import csv
from copy import deepcopy
from datetime import datetime
from io import StringIO
import json
import re

from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
import stripe

from ..auth import admin_required
from ..constants import DATETIME_FORMAT
from ..errors import flash_success
from ..events.models import (
    Audience,
    Event,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from ..events.templates import (
    apply_template,
    load_event_templates,
    validate_price_option,
    validate_question,
)
from ..models import db
from .payments import refund_or_cancel_payment


admin_events_bp = Blueprint("admin_events", __name__)

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REGISTRATION_BASE_COLUMNS = [
    ("id", "ID"),
    ("status", "Status"),
    ("price_option_name", "Price option"),
    ("team_name", "Team name"),
    ("contact_email", "Contact email"),
    ("contact_phone", "Contact phone"),
    ("emergency_contact", "Emergency contact"),
]
_REGISTRATION_TRAILING_COLUMNS = [
    ("amount_cents", "Amount"),
    ("discount_applied", "Discount applied"),
    ("created_at", "Created at"),
]
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _parse_event_fields(form):
    slug = (form.get("slug") or "").strip()
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            "Slug must contain only lowercase letters, numbers, and hyphens."
        )

    name = (form.get("name") or "").strip()
    location = (form.get("location") or "").strip()
    if not name:
        raise ValueError("Event name is required.")
    if not location:
        raise ValueError("Location is required.")

    try:
        event_date = datetime.strptime(
            form.get("event_date", ""),
            DATETIME_FORMAT,
        )
        signup_start = datetime.strptime(
            form.get("signup_start", ""),
            DATETIME_FORMAT,
        )
        signup_end = datetime.strptime(
            form.get("signup_end", ""),
            DATETIME_FORMAT,
        )
    except ValueError as exc:
        raise ValueError(
            "Event date and signup dates must be valid date-times."
        ) from exc

    if signup_start >= signup_end:
        raise ValueError("Signup start must be before signup end.")

    capacity_text = (form.get("capacity") or "").strip()
    capacity = None
    if capacity_text:
        try:
            capacity = int(capacity_text)
        except ValueError as exc:
            raise ValueError("Capacity must be a whole number.") from exc
        if capacity < 0:
            raise ValueError("Capacity cannot be negative.")

    status = form.get("status", EventStatus.DRAFT)
    if status not in EventStatus.ALL:
        raise ValueError(f"Invalid event status '{status}'.")

    audience = form.get("audience", Audience.BOTH)
    if audience not in Audience.ALL:
        raise ValueError(f"Invalid audience '{audience}'.")

    return {
        "slug": slug,
        "name": name,
        "description": (form.get("description") or "").strip(),
        "location": location,
        "event_date": event_date,
        "signup_start": signup_start,
        "signup_end": signup_end,
        "capacity": capacity,
        "status": status,
        "audience": audience,
        "details_url": (form.get("details_url") or "").strip() or None,
        "discount_code": (
            (form.get("discount_code") or "").strip() or None
        ),
    }


def _parse_json_rows(raw_value, field_label):
    try:
        rows = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field_label} must contain valid JSON.") from exc
    if not isinstance(rows, list):
        raise ValueError(f"{field_label} must be a JSON list.")
    return rows


def _validated_price_options(raw_value):
    rows = _parse_json_rows(raw_value, "Price options")
    seen_ids = set()
    validated = []
    for index, row in enumerate(rows):
        validate_price_option(row, index)
        row = deepcopy(row)
        option_id = row.get("id")
        if option_id is not None:
            if isinstance(option_id, bool):
                raise ValueError("Price option IDs must be whole numbers.")
            try:
                option_id = int(option_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Price option IDs must be whole numbers."
                ) from exc
            if option_id in seen_ids:
                raise ValueError(
                    f"Price option ID {option_id} was submitted twice."
                )
            seen_ids.add(option_id)
            row["id"] = option_id

        active = row.get("active", True)
        if not isinstance(active, bool):
            raise ValueError(
                f"Price option {index + 1} field 'active' must be a bool."
            )
        row["active"] = active
        row["participant_roles"] = row.get(
            "participant_roles",
            ["Participant"],
        )
        validated.append(row)
    return validated


def _replace_price_options(event, raw_value):
    rows = _validated_price_options(raw_value)
    existing = list(event.price_options)
    existing_by_id = {
        option.id: option for option in existing if option.id is not None
    }
    submitted_ids = {
        row["id"] for row in rows if row.get("id") is not None
    }

    unknown_ids = submitted_ids - set(existing_by_id)
    if unknown_ids:
        unknown = min(unknown_ids)
        raise ValueError(
            f"Price option ID {unknown} does not belong to this event."
        )

    for option in existing:
        if option.id in submitted_ids:
            continue
        if option.registrations:
            raise ValueError(
                f"Price option '{option.name}' cannot be removed because "
                "it has registrations."
            )

    for option in existing:
        if option.id not in submitted_ids:
            event.price_options.remove(option)

    for index, row in enumerate(rows):
        option_id = row.get("id")
        if option_id is None:
            option = EventPriceOption()
            event.price_options.append(option)
        else:
            option = existing_by_id[option_id]

        option.name = row["name"].strip()
        option.description = (row.get("description") or "").strip() or None
        option.price_cents = row["price_cents"]
        option.member_price_cents = row.get("member_price_cents")
        option.participant_roles = deepcopy(row["participant_roles"])
        option.sort_order = index
        option.active = row["active"]


def _validated_questions(raw_value, option_names=None):
    rows = _parse_json_rows(raw_value, "Custom questions")
    known_names = set(option_names or ())
    scopes_by_key: dict[str, list[set[str]]] = {}
    validated = []
    for index, row in enumerate(rows):
        validate_question(row, index)
        row = deepcopy(row)
        key = row["key"]
        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                f"Custom question {index + 1} must have a non-empty key."
            )
        key = key.strip()
        scope = _validated_question_scope(row, index, known_names)
        _check_scope_is_disjoint(key, scope, scopes_by_key.get(key, []))
        scopes_by_key.setdefault(key, []).append(scope)
        row["key"] = key
        row["options"] = row.get("options", [])
        row["help_text"] = row.get("help_text") or ""
        row["price_options"] = sorted(scope)
        validated.append(row)
    return validated


def _validated_question_scope(row, index, known_names):
    """Return the question's price-option scope as a set of known names."""
    scope = row.get("price_options") or []
    names = {name.strip() for name in scope if isinstance(name, str)}
    names.discard("")
    if known_names:
        unknown = names - known_names
        if unknown:
            raise ValueError(
                f"Custom question {index + 1} is limited to price option "
                f"'{min(unknown)}', which does not exist on this event."
            )
    return names


def _check_scope_is_disjoint(key, scope, existing_scopes):
    """Allow a repeated key only when every scope sharing it is disjoint."""
    if not existing_scopes:
        return
    if not scope or any(not other for other in existing_scopes):
        raise ValueError(
            f"Custom question key '{key}' is duplicated. Repeat a key only "
            "when each copy is limited to different price options."
        )
    for other in existing_scopes:
        overlap = scope & other
        if overlap:
            raise ValueError(
                f"Custom question key '{key}' is used twice for price "
                f"option '{min(overlap)}'."
            )


def _serialize_price_options(event):
    if event is None:
        return []
    return [
        {
            "id": option.id,
            "name": option.name,
            "description": option.description or "",
            "price_cents": option.price_cents,
            "member_price_cents": option.member_price_cents,
            "participant_roles": option.participant_roles or [],
            "sort_order": option.sort_order,
            "active": option.active,
        }
        for option in event.price_options
    ]


def _editor_template_data(templates):
    return {
        key: {
            "price_options": deepcopy(template["price_options"]),
            "custom_questions": deepcopy(template["custom_questions"]),
        }
        for key, template in templates.items()
    }


def _render_form(event=None, error=None, status_code=200):
    templates = load_event_templates()
    submitted_prices = request.form.get("price_options_json")
    submitted_questions = request.form.get("custom_questions_json")
    prices_json = (
        submitted_prices
        if submitted_prices is not None
        else json.dumps(_serialize_price_options(event))
    )
    questions_json = (
        submitted_questions
        if submitted_questions is not None
        else json.dumps(event.custom_questions if event else [])
    )
    return (
        render_template(
            "admin/event_form.html",
            event=event,
            form_data=request.form if request.method == "POST" else None,
            templates=templates,
            template_editor_data=_editor_template_data(templates),
            price_options_json=prices_json,
            custom_questions_json=questions_json,
            error=error,
        ),
        status_code,
    )


def _event_rows():
    rows = []
    events = Event.query.order_by(Event.event_date.desc()).all()
    for event in events:
        revenue_cents = sum(
            registration.amount_cents
            for registration in event.registrations
            if registration.status == RegistrationStatus.CONFIRMED
        )
        rows.append(
            {
                "id": event.id,
                "name": event.name,
                "slug": event.slug,
                "event_date": event.event_date.isoformat(),
                "audience": event.audience,
                "status": event.status,
                "confirmed_count": event.confirmed_count,
                "capacity": event.capacity,
                "revenue_cents": revenue_cents,
                "template_key": event.template_key,
            }
        )
    return rows


def _registration_columns(event):
    max_participants = max(
        [
            len(option.participant_roles or [])
            for option in event.price_options
        ]
        + [len(registration.participants) for registration in event.registrations]
        + [0]
    )
    participant_columns = [
        (f"participant_{position}", f"Participant {position}")
        for position in range(1, max_participants + 1)
    ]
    # A key may repeat across price-option scopes; it is still one column.
    question_columns = []
    seen_question_keys = set()
    for question in event.custom_questions or []:
        key = question["key"]
        if key in seen_question_keys:
            continue
        seen_question_keys.add(key)
        question_columns.append((key, question.get("label") or key))
    return (
        _REGISTRATION_BASE_COLUMNS
        + participant_columns
        + question_columns
        + _REGISTRATION_TRAILING_COLUMNS
    )


def _display_answer(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _sanitize_csv_value(value):
    if isinstance(value, str) and value.startswith(
        _CSV_FORMULA_PREFIXES
    ):
        return f"'{value}"
    return value


def _registration_rows(event):
    columns = _registration_columns(event)
    column_keys = [key for key, _label in columns]
    rows = []
    registrations = sorted(
        event.registrations,
        key=lambda registration: registration.created_at,
        reverse=True,
    )
    for registration in registrations:
        emergency_contact = registration.emergency_contact_name or ""
        if registration.emergency_contact_phone:
            emergency_contact = (
                f"{emergency_contact} "
                f"({registration.emergency_contact_phone})"
            ).strip()

        row = {
            "id": registration.id,
            "status": registration.status,
            "price_option_name": (
                registration.price_option.name
                if registration.price_option
                else ""
            ),
            "team_name": registration.team_name or "",
            "contact_email": registration.contact_email,
            "contact_phone": registration.contact_phone,
            "emergency_contact": emergency_contact,
            "amount_cents": registration.amount_cents,
            "discount_applied": registration.discount_applied,
            "created_at": registration.created_at.isoformat(),
        }
        for position, participant in enumerate(
            registration.participants,
            start=1,
        ):
            row[f"participant_{position}"] = (
                f"{participant.role_label}: {participant.name} "
                f"({participant.date_of_birth.isoformat()}, "
                f"{participant.email}, {participant.phone})"
            )
        for question in event.custom_questions or []:
            key = question["key"]
            row[key] = _display_answer(
                (registration.answers or {}).get(key)
            )
        rows.append({key: row.get(key, "") for key in column_keys})
    return columns, rows


@admin_events_bp.route("/admin/events")
@admin_required
def events_page():
    return render_template("admin/events.html")


@admin_events_bp.route("/admin/events/data")
@admin_required
def events_data():
    return jsonify({"events": _event_rows()})


@admin_events_bp.route("/admin/events/new", methods=["GET", "POST"])
@admin_required
def new_event():
    if request.method == "GET":
        return _render_form()

    try:
        fields = _parse_event_fields(request.form)
        if Event.query.filter_by(slug=fields["slug"]).first():
            raise ValueError(
                f"An event with slug '{fields['slug']}' already exists."
            )

        event = Event(**fields)
        template_key = request.form.get("template_key", "blank")
        apply_template(event, template_key)

        price_rows = request.form.get("price_options_json")
        if price_rows is not None:
            _replace_price_options(event, price_rows)
        question_rows = request.form.get("custom_questions_json")
        if question_rows is not None:
            event.custom_questions = _validated_questions(
                question_rows,
                [option.name for option in event.price_options],
            )

        db.session.add(event)
        db.session.commit()
        flash_success("Event created successfully.")
        return redirect(url_for("admin_events.events_page"))
    except ValueError as exc:
        db.session.rollback()
        return _render_form(error=str(exc), status_code=400)


@admin_events_bp.route(
    "/admin/events/<int:event_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def edit_event(event_id):
    event = db.get_or_404(Event, event_id)
    if request.method == "GET":
        return _render_form(event=event)

    try:
        fields = _parse_event_fields(request.form)
        slug_owner = Event.query.filter_by(slug=fields["slug"]).first()
        if slug_owner and slug_owner.id != event.id:
            raise ValueError(
                f"An event with slug '{fields['slug']}' already exists."
            )
        for field, value in fields.items():
            setattr(event, field, value)

        price_rows = request.form.get("price_options_json")
        if price_rows is not None:
            _replace_price_options(event, price_rows)
        question_rows = request.form.get("custom_questions_json")
        if question_rows is not None:
            event.custom_questions = _validated_questions(
                question_rows,
                [option.name for option in event.price_options],
            )

        db.session.commit()
        flash_success("Event updated successfully.")
        return redirect(url_for("admin_events.events_page"))
    except ValueError as exc:
        db.session.rollback()
        event = db.get_or_404(Event, event_id)
        return _render_form(
            event=event,
            error=str(exc),
            status_code=400,
        )


@admin_events_bp.route(
    "/admin/events/<int:event_id>/duplicate",
    methods=["POST"],
)
@admin_required
def duplicate_event(event_id):
    event = db.get_or_404(Event, event_id)
    base_slug = f"{event.slug}-copy"
    slug = base_slug
    suffix = 2
    while Event.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    duplicate = Event(
        slug=slug,
        name=f"{event.name} (Copy)",
        description=event.description,
        location=event.location,
        event_date=event.event_date,
        signup_start=event.signup_start,
        signup_end=event.signup_end,
        capacity=event.capacity,
        status=EventStatus.DRAFT,
        audience=event.audience,
        details_url=event.details_url,
        discount_code=event.discount_code,
        custom_questions=deepcopy(event.custom_questions or []),
        template_key=event.template_key,
    )
    for option in event.price_options:
        duplicate.price_options.append(
            EventPriceOption(
                name=option.name,
                description=option.description,
                price_cents=option.price_cents,
                member_price_cents=option.member_price_cents,
                participant_roles=deepcopy(
                    option.participant_roles or []
                ),
                sort_order=option.sort_order,
                active=option.active,
            )
        )

    db.session.add(duplicate)
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "event": {"id": duplicate.id, "slug": duplicate.slug},
            "message": "Event duplicated as a draft.",
        }
    )


@admin_events_bp.route(
    "/admin/events/<int:event_id>/delete",
    methods=["POST"],
)
@admin_required
def delete_event(event_id):
    event = db.get_or_404(Event, event_id)
    if event.status != EventStatus.DRAFT:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Only draft events can be deleted.",
                }
            ),
            409,
        )
    if event.registrations:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "This draft cannot be deleted because it has "
                        "registrations."
                    ),
                }
            ),
            409,
        )
    db.session.delete(event)
    db.session.commit()
    return jsonify({"success": True, "message": "Event deleted."})


@admin_events_bp.route(
    "/admin/events/<int:event_id>/status",
    methods=["POST"],
)
@admin_required
def set_event_status(event_id):
    event = db.get_or_404(Event, event_id)
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in EventStatus.ALL:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Status must be one of: draft, active, closed."
                    ),
                }
            ),
            400,
        )
    event.status = status
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "status": event.status,
            "message": f"Event status changed to {event.status}.",
        }
    )


@admin_events_bp.route(
    "/admin/events/<int:event_id>/registrations"
)
@admin_required
def event_registrations(event_id):
    event = db.get_or_404(Event, event_id)
    option_counts = [
        {
            "name": option.name,
            "count": sum(
                registration.status == RegistrationStatus.CONFIRMED
                for registration in option.registrations
            ),
        }
        for option in event.price_options
    ]
    return render_template(
        "admin/event_registrations.html",
        event=event,
        option_counts=option_counts,
    )


@admin_events_bp.route(
    "/admin/events/<int:event_id>/registrations/data"
)
@admin_required
def event_registrations_data(event_id):
    event = db.get_or_404(Event, event_id)
    columns, rows = _registration_rows(event)
    return jsonify(
        {
            "columns": [
                {"key": key, "label": label}
                for key, label in columns
            ],
            "registrations": rows,
        }
    )


@admin_events_bp.route(
    "/admin/events/<int:event_id>/registrations/export.csv"
)
@admin_required
def export_event_registrations(event_id):
    event = db.get_or_404(Event, event_id)
    columns, rows = _registration_rows(event)
    fieldnames = [key for key, _label in columns]
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(
        {
            key: _sanitize_csv_value(value)
            for key, value in row.items()
        }
        for row in rows
    )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename="
                f'"registrations-{event.slug}.csv"'
            )
        },
    )


@admin_events_bp.route(
    "/admin/events/registrations/<int:registration_id>/cancel",
    methods=["POST"],
)
@admin_required
def cancel_event_registration(registration_id):
    registration = db.get_or_404(
        EventRegistration,
        registration_id,
    )
    succeeded_payment = next(
        (
            payment
            for payment in registration.payments
            if payment.status == "succeeded"
        ),
        None,
    )

    try:
        if succeeded_payment is not None:
            refund_or_cancel_payment(succeeded_payment)
            registration.status = RegistrationStatus.REFUNDED
            message = "Registration refunded."
        elif registration.status == RegistrationStatus.PENDING_PAYMENT:
            registration.status = RegistrationStatus.CANCELLED
            message = "Registration cancelled."
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "Only pending unpaid or paid registrations "
                            "can be cancelled."
                        ),
                    }
                ),
                400,
            )
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "status": registration.status,
                "message": message,
            }
        )
    except (ValueError, stripe.error.StripeError) as exc:
        db.session.rollback()
        return (
            jsonify({"success": False, "error": str(exc)}),
            400,
        )
