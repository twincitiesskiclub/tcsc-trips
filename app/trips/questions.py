"""One ordered trip-question list: built-ins and custom questions.

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

DIETARY_OTHER = "Other (specify below)"
DIETARY_OPTIONS = [
    "None", "Vegan", "Vegetarian", "Gluten-Free", "Dairy Free / Lactose Intolerant",
    "Nut allergy", "Halal", "Kosher", "Pescatarian", DIETARY_OTHER,
]
# Defaults are expanded into stored entries, never implicitly added at render or
# submission time. The data migration uses these same initial defaults.
BUILTIN_QUESTIONS = {
    "carpool": {
        "builtin": "carpool", "label": "Can you drive a carpool?",
        "help_text": "", "required": True, "enabled": True,
        "followups": {
            "seats": {"label": "How many people can you accommodate (besides yourself)?",
                      "help_text": "", "enabled": True},
            "bikes": {"label": "How many bikes can you accommodate?",
                      "help_text": "", "enabled": True},
            "hitch": {"label": "Do you have a trailer hitch?",
                      "help_text": "", "enabled": True},
        },
    },
    "region_code": {
        "builtin": "region_code", "label": "What is your region code?",
        "help_text": "Find your code on the TCSC region map.",
        "required": True, "enabled": True,
    },
    "dietary": {
        "builtin": "dietary", "label": "Dietary restrictions",
        "help_text": "Select all that apply.", "required": False,
        "enabled": True, "options": DIETARY_OPTIONS,
        "followups": {
            "other": {"label": "Other dietary restriction(s)?", "help_text": ""},
        },
    },
    "tent": {
        "builtin": "tent", "label": "Do you have a 2+ person tent?",
        "help_text": "", "required": False, "enabled": True,
    },
}
BUILTIN_ANSWER_TYPES = {
    "carpool": "Carpool details", "region_code": "Text (up to 10 characters)",
    "dietary": "Multiple choice and other text", "tent": "Yes or no",
}


def default_builtin_questions():
    return deepcopy(list(BUILTIN_QUESTIONS.values()))


def expand_builtin(question):
    """Expand YAML shorthand without sharing mutable defaults between trips."""
    if isinstance(question, dict) and "builtin" in question:
        builtin = question["builtin"]
        if not isinstance(builtin, str) or builtin not in BUILTIN_QUESTIONS:
            raise ValueError(f"Unknown built-in question {builtin!r}")
        expanded = deepcopy(BUILTIN_QUESTIONS[builtin] | question)
        defaults = BUILTIN_QUESTIONS[builtin].get("followups")
        if defaults and isinstance(question.get("followups"), dict):
            for key, fields in defaults.items():
                override = expanded["followups"].get(key, {})
                if isinstance(override, dict):
                    expanded["followups"][key] = deepcopy(fields) | override
        return expanded
    return deepcopy(question)


def enabled_questions(questions):
    return [q for q in questions or [] if "builtin" not in q or q["enabled"]]


def _validate_builtin(question, name):
    builtin = question["builtin"]
    if not isinstance(builtin, str) or builtin not in BUILTIN_QUESTIONS:
        raise ValueError(f"{name}: unknown built-in question {builtin!r}")
    allowed = {"builtin", "label", "help_text", "required", "enabled"}
    if builtin == "dietary":
        allowed.add("options")
    if builtin in ("carpool", "dietary"):
        allowed.add("followups")
    if set(question) - allowed:
        raise ValueError(f"{name}: built-in keys and answer types are fixed; "
                         "unsupported fields: " + ", ".join(sorted(set(question) - allowed)))
    if not isinstance(question.get("label"), str) or not question["label"].strip():
        raise ValueError(f"{name}: label must be non-empty text")
    if "help_text" in question and not isinstance(question["help_text"], str):
        raise ValueError(f"{name}: help_text must be text")
    for field in ("required", "enabled"):
        if not isinstance(question.get(field), bool):
            raise ValueError(f"{name} field '{field}' must be a bool")
    if builtin in ("carpool", "dietary"):
        followups = question.get("followups")
        if not isinstance(followups, dict):
            raise ValueError(f"{name}: followups must be a mapping")
        keys = {"seats", "bikes", "hitch"} if builtin == "carpool" else {"other"}
        if set(followups) != keys:
            raise ValueError(f"{name}: {builtin} followups must contain exactly "
                             + ", ".join(sorted(keys)))
        fields = {"label", "help_text", "enabled"} if builtin == "carpool" else {"label", "help_text"}
        for key, followup in followups.items():
            followup_name = f"{name} followup '{key}'"
            if not isinstance(followup, dict):
                raise ValueError(f"{followup_name} must be a mapping")
            if set(followup) != fields:
                raise ValueError(f"{followup_name} must contain exactly "
                                 + ", ".join(sorted(fields)))
            if not isinstance(followup["label"], str) or not followup["label"].strip():
                raise ValueError(f"{followup_name}: label must be non-empty text")
            if not isinstance(followup["help_text"], str):
                raise ValueError(f"{followup_name}: help_text must be text")
            if builtin == "carpool" and not isinstance(followup["enabled"], bool):
                raise ValueError(f"{followup_name} field 'enabled' must be a bool")
    if builtin == "dietary":
        options = question.get("options")
        if (not isinstance(options, list) or not options
                or any(not isinstance(o, str) or not o.strip() or o != o.strip()
                       for o in options)):
            raise ValueError(f"{name}: dietary options must be a non-empty list of non-empty text")
        if options.count(DIETARY_OTHER) != 1:
            raise ValueError(f"{name}: dietary options must include exactly one '{DIETARY_OTHER}'")
        if len(set(options)) != len(options):
            raise ValueError(f"{name}: dietary options must be unique")


QUESTION_TYPES = {"text", "choice", "multi_choice", "yes_no"}
_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
RESERVED_QUESTION_KEYS = frozenset({
    "id", "member", "email", "status", "price_tier",
    "can_drive", "seat_capacity", "bike_capacity", "hitch_size",
    "region_code", "dietary", "dietary_restrictions", "dietary_other",
    "has_tent", "amount_cents", "payment_status", "payment_id", "created_at",
})  # roster/system column keys; keep in sync with admin.py's _TRIP_REG_* constants


def _offender(index, question):
    key = question.get("key") if isinstance(question, dict) else None
    return f"Question '{key}'" if key else f"Question {index + 1}"


def validate_trip_question(question, index=0):
    name = _offender(index, question)
    if not isinstance(question, dict):
        raise ValueError(f"{name} must be a mapping")
    if "builtin" in question:
        _validate_builtin(question, name)
        return
    for field in ("key", "label", "type", "required"):
        if field not in question:
            raise ValueError(f"{name} is missing '{field}'")
    if not isinstance(question["key"], str) or not _KEY_PATTERN.match(question["key"]):
        raise ValueError(
            f"{name} key must match [a-z0-9_]+ (got {question['key']!r})")
    if question["key"] in RESERVED_QUESTION_KEYS:
        raise ValueError(
            f"{name} key '{question['key']}' is reserved for system columns")
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
    (unique custom keys and built-in ids; visible_if targets an EARLIER
    custom yes_no question)."""
    if not isinstance(questions, list):
        raise ValueError("Custom questions must be a list")
    seen = {}
    builtins = set()
    for index, question in enumerate(questions):
        validate_trip_question(question, index)
        if "builtin" in question:
            builtin = question["builtin"]
            if builtin in builtins:
                raise ValueError(f"Built-in question '{builtin}' is duplicated.")
            builtins.add(builtin)
            continue
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
            template["custom_questions"] = [
                expand_builtin(q) for q in template["custom_questions"]]
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
