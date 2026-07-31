"""Trip custom-question schema: validation + template library.

Parallel to app/events/templates.py, with three additions the trip forms
need: multi_choice (with an optional pick-up-to-N cap), yes_no, and
visible_if conditional display keyed to an earlier yes_no question.
"""
from copy import deepcopy
from pathlib import Path
import re

import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "trip_templates.yaml"
_template_cache = None

QUESTION_TYPES = {"text", "choice", "multi_choice", "yes_no"}
_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _offender(index, question):
    key = question.get("key") if isinstance(question, dict) else None
    return f"Question '{key}'" if key else f"Question {index + 1}"


def validate_trip_question(question, index=0):
    name = _offender(index, question)
    if not isinstance(question, dict):
        raise ValueError(f"{name} must be a mapping")
    for field in ("key", "label", "type", "required"):
        if field not in question:
            raise ValueError(f"{name} is missing '{field}'")
    if not isinstance(question["key"], str) or not _KEY_PATTERN.match(question["key"]):
        raise ValueError(
            f"{name} key must match [a-z0-9_]+ (got {question['key']!r})")
    qtype = question["type"]
    if qtype not in QUESTION_TYPES:
        raise ValueError(f"{name} has invalid type '{qtype}'")
    if not isinstance(question["required"], bool):
        raise ValueError(f"{name} field 'required' must be a bool")
    if qtype in ("choice", "multi_choice"):
        if not isinstance(question.get("options"), list) or not question["options"]:
            raise ValueError(f"{name} must have a non-empty 'options' list")
    if "max_selections" in question and question["max_selections"] is not None:
        if qtype != "multi_choice":
            raise ValueError(f"{name}: max_selections only applies to multi_choice")
        cap = question["max_selections"]
        if type(cap) is not int or cap < 1:
            raise ValueError(f"{name}: max_selections must be a positive int")
    visible_if = question.get("visible_if")
    if visible_if is not None:
        if (not isinstance(visible_if, dict)
                or set(visible_if) != {"question", "equals"}
                or visible_if["equals"] not in ("yes", "no")):
            raise ValueError(
                f"{name}: visible_if must be "
                "{'question': <key>, 'equals': 'yes'|'no'}")


def validate_questions(questions):
    """Validate a full list: per-question rules plus cross-question rules
    (unique keys; visible_if targets an EARLIER yes_no question)."""
    if not isinstance(questions, list):
        raise ValueError("Custom questions must be a list")
    seen = {}
    for index, question in enumerate(questions):
        validate_trip_question(question, index)
        key = question["key"]
        if key in seen:
            raise ValueError(f"Question key '{key}' is duplicated.")
        visible_if = question.get("visible_if")
        if visible_if is not None:
            target = visible_if["question"]
            if target not in seen:
                raise ValueError(
                    f"Question '{key}': visible_if must reference an "
                    f"earlier question (got '{target}').")
            if seen[target]["type"] != "yes_no":
                raise ValueError(
                    f"Question '{key}': visible_if target '{target}' "
                    "must be a yes_no question.")
        seen[key] = question


def load_trip_templates():
    global _template_cache
    if _template_cache is None:
        try:
            with open(_CONFIG_PATH) as handle:
                config = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"trip_templates.yaml is invalid YAML: {exc}")
        templates = (config or {}).get("templates")
        if not isinstance(templates, dict):
            raise ValueError("trip_templates.yaml must have a 'templates' mapping")
        for key, template in templates.items():
            if "name" not in template:
                raise ValueError(f"Template '{key}' is missing 'name'")
            if not isinstance(template.get("custom_questions"), list):
                raise ValueError(
                    f"Template '{key}' field 'custom_questions' must be a list")
            validate_questions(template["custom_questions"])
        _template_cache = templates
    return _template_cache


def get_template(key):
    return load_trip_templates().get(key)


def apply_template(trip, template_key):
    template = get_template(template_key)
    if template is None:
        raise ValueError(f"Unknown trip template '{template_key}'")
    trip.template_key = template_key
    trip.custom_questions = deepcopy(template["custom_questions"])


def _reset_cache():
    global _template_cache
    _template_cache = None
