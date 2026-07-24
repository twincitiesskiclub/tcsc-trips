"""Load and apply reusable event registration templates."""

from copy import deepcopy
from pathlib import Path

import yaml

from app.events.models import Event, EventPriceOption


_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "event_templates.yaml"
)
_template_cache: dict[str, dict] | None = None


def _question_name(template_key, index, question):
    key = question.get("key") if isinstance(question, dict) else None
    identifier = f"'{key}'" if key else str(index + 1)
    return f"Template '{template_key}' question {identifier}"


def _validate_question(template_key, index, question):
    offender = _question_name(template_key, index, question)
    if not isinstance(question, dict):
        raise ValueError(f"{offender} must be a mapping")

    for field in ("key", "label", "type", "required"):
        if field not in question:
            raise ValueError(f"{offender} is missing '{field}'")

    if question["type"] not in {"choice", "text"}:
        raise ValueError(
            f"{offender} has invalid type '{question['type']}'"
        )
    if not isinstance(question["required"], bool):
        raise ValueError(f"{offender} field 'required' must be a bool")
    if question["type"] == "choice" and not isinstance(
        question.get("options"), list
    ):
        raise ValueError(f"{offender} must have an 'options' list")


def _validate_templates(config):
    if not isinstance(config, dict):
        raise ValueError("Event templates config must be a mapping")

    templates = config.get("templates")
    if not isinstance(templates, dict):
        raise ValueError(
            "Event templates config must contain a 'templates' mapping"
        )

    for template_key, template in templates.items():
        if not isinstance(template, dict):
            raise ValueError(f"Template '{template_key}' must be a mapping")
        for field in ("name", "price_options", "custom_questions"):
            if field not in template:
                raise ValueError(
                    f"Template '{template_key}' is missing '{field}'"
                )
        if not isinstance(template["price_options"], list):
            raise ValueError(
                f"Template '{template_key}' field 'price_options' "
                "must be a list"
            )
        if not isinstance(template["custom_questions"], list):
            raise ValueError(
                f"Template '{template_key}' field 'custom_questions' "
                "must be a list"
            )
        for index, question in enumerate(template["custom_questions"]):
            _validate_question(template_key, index, question)

    return templates


def load_event_templates() -> dict[str, dict]:
    """Load, validate, and cache event templates from YAML."""
    global _template_cache
    if _template_cache is None:
        try:
            with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"Malformed event templates YAML: {exc}"
            ) from exc
        _template_cache = _validate_templates(config)
    return _template_cache


def get_template(key: str) -> dict | None:
    """Return the configured template for ``key``, if one exists."""
    return load_event_templates().get(key)


def apply_template(event: Event, template_key: str) -> None:
    """Copy a configured template onto an Event without committing it."""
    template = get_template(template_key)
    if template is None:
        raise ValueError(f"Unknown event template '{template_key}'")

    event.template_key = template_key
    event.custom_questions = deepcopy(template["custom_questions"])

    for index, option in enumerate(template["price_options"]):
        event.price_options.append(
            EventPriceOption(
                name=option["name"],
                description=option.get("description"),
                price_cents=option["price_cents"],
                member_price_cents=option.get("member_price_cents"),
                participant_roles=deepcopy(
                    option.get("participant_roles", ["Participant"])
                ),
                sort_order=option.get("sort_order", index),
                active=option.get("active", True),
            )
        )


def _reset_cache() -> None:
    """Clear the template cache for tests."""
    global _template_cache
    _template_cache = None
