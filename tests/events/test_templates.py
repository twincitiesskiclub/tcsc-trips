from datetime import datetime

import pytest

from app.events.models import Event
from app.events import templates as event_templates


@pytest.fixture(autouse=True)
def reset_template_cache():
    event_templates._reset_cache()
    yield
    event_templates._reset_cache()


def _event():
    return Event(
        slug="dry-tri-2026",
        name="Dry Tri",
        location="Carver Park",
        event_date=datetime(2026, 10, 24, 9, 0),
        signup_start=datetime(2026, 8, 1),
        signup_end=datetime(2026, 10, 22),
    )


def test_load_event_templates():
    templates = event_templates.load_event_templates()

    assert set(templates) == {"dry_tri", "social", "blank"}
    assert templates["dry_tri"]["name"] == "Dry Tri (race)"
    assert event_templates.load_event_templates() is templates


def test_dry_tri_price_options():
    template = event_templates.get_template("dry_tri")

    assert [option["price_cents"] for option in template["price_options"]] == [
        5500,
        10500,
        3000,
    ]
    assert template["price_options"][1]["participant_roles"] == [
        "Rollerskier",
        "Mountain Biker",
        "Trail Runner",
    ]


def test_apply_template_copies_questions_and_price_options(db_session):
    event = _event()
    event_templates.apply_template(event, "dry_tri")
    db_session.session.add(event)
    db_session.session.commit()
    event_id = event.id

    configured_template = event_templates.get_template("dry_tri")
    configured_template["custom_questions"][0]["label"] = "Edited label"
    configured_template["price_options"][1]["participant_roles"].append(
        "Edited role"
    )

    db_session.session.expire_all()
    saved_event = db_session.session.get(Event, event_id)

    assert saved_event.template_key == "dry_tri"
    assert len(saved_event.custom_questions) == 5
    assert saved_event.custom_questions[0]["label"] == "Competition gender"
    assert [option.name for option in saved_event.price_options] == [
        "Individual",
        "Team of 3",
        "Run-only 6K",
    ]
    assert saved_event.price_options[1].participant_roles == [
        "Rollerskier",
        "Mountain Biker",
        "Trail Runner",
    ]
    assert [option.sort_order for option in saved_event.price_options] == [
        0,
        1,
        2,
    ]
    assert all(option.active for option in saved_event.price_options)


def test_get_template_returns_none_for_unknown_key():
    assert event_templates.get_template("not-a-template") is None


def test_malformed_question_raises_value_error(tmp_path, monkeypatch):
    config_path = tmp_path / "event_templates.yaml"
    config_path.write_text(
        """
templates:
  broken:
    name: Broken
    price_options: []
    custom_questions:
      - label: Missing key
        type: text
        required: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(event_templates, "_CONFIG_PATH", config_path)

    with pytest.raises(ValueError, match=r"broken.*question.*key"):
        event_templates.load_event_templates()


def test_question_with_bad_type_raises_value_error(tmp_path, monkeypatch):
    config_path = tmp_path / "event_templates.yaml"
    config_path.write_text(
        """
templates:
  broken:
    name: Broken
    price_options: []
    custom_questions:
      - key: format
        label: Format
        type: number
        required: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(event_templates, "_CONFIG_PATH", config_path)

    with pytest.raises(ValueError, match=r"broken.*question.*invalid type"):
        event_templates.load_event_templates()


def test_choice_question_without_options_raises_value_error(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "event_templates.yaml"
    config_path.write_text(
        """
templates:
  broken:
    name: Broken
    price_options: []
    custom_questions:
      - key: format
        label: Format
        type: choice
        required: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(event_templates, "_CONFIG_PATH", config_path)

    with pytest.raises(ValueError, match=r"broken.*question.*options"):
        event_templates.load_event_templates()


def test_price_option_without_price_raises_value_error(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "event_templates.yaml"
    config_path.write_text(
        """
templates:
  broken:
    name: Broken
    price_options:
      - name: Registration
    custom_questions: []
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(event_templates, "_CONFIG_PATH", config_path)

    with pytest.raises(
        ValueError, match=r"broken.*price option.*Registration.*price_cents"
    ):
        event_templates.load_event_templates()


def test_apply_template_with_unknown_key_raises_value_error():
    with pytest.raises(ValueError, match=r"Unknown event template 'missing'"):
        event_templates.apply_template(_event(), "missing")
