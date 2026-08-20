import pytest

from app.trips import questions as tq


def _q(**overrides):
    base = {"key": "chore", "label": "Which task do you prefer?",
            "type": "choice", "options": ["Cooking", "Cleaning"],
            "required": True}
    base.update(overrides)
    return base


def test_valid_question_passes():
    tq.validate_trip_question(_q())


def test_missing_field_raises():
    q = _q()
    del q["label"]
    with pytest.raises(ValueError, match="missing 'label'"):
        tq.validate_trip_question(q)


def test_reserved_key_raises():
    with pytest.raises(ValueError, match="reserved"):
        tq.validate_trip_question(_q(key="status"))


def test_invalid_type_raises():
    with pytest.raises(ValueError, match="invalid type"):
        tq.validate_trip_question(_q(type="dropdown"))


def test_multi_choice_max_selections_must_be_positive_int():
    with pytest.raises(ValueError, match="max_selections"):
        tq.validate_trip_question(
            _q(type="multi_choice", max_selections=0))


def test_visible_if_must_reference_earlier_yes_no():
    qs = [
        _q(key="depart", type="text", options=[]),
        _q(key="follow", visible_if={"question": "depart", "equals": "yes"}),
    ]
    with pytest.raises(ValueError, match="yes_no"):
        tq.validate_questions(qs)


def test_visible_if_forward_reference_rejected():
    qs = [
        _q(key="follow", visible_if={"question": "later", "equals": "yes"}),
        _q(key="later", type="yes_no", options=[]),
    ]
    with pytest.raises(ValueError, match="earlier"):
        tq.validate_questions(qs)


def test_duplicate_key_rejected():
    with pytest.raises(ValueError, match="duplicated"):
        tq.validate_questions([_q(key="a"), _q(key="a")])


def test_templates_load_and_validate():
    tq._reset_cache()
    templates = tq.load_trip_templates()
    for expected in ("race_weekend", "cuyuna_camping", "pre_birkie",
                     "sisu", "birkie", "gbc", "hayward", "blank"):
        assert expected in templates
    for template in templates.values():
        tq.validate_questions(template["custom_questions"])


def test_visible_if_happy_path_validates():
    qs = [
        _q(key="can_stop", type="yes_no", options=[]),
        _q(key="stop_where", type="text", options=[],
           visible_if={"question": "can_stop", "equals": "yes"}),
    ]
    tq.validate_questions(qs)  # must not raise


def test_apply_template_deep_copies():
    tq._reset_cache()
    template = tq.get_template("gbc")
    class FakeTrip:
        custom_questions = None
        template_key = None
    trip = FakeTrip()
    tq.apply_template(trip, "gbc")
    assert trip.template_key == "gbc"
    trip.custom_questions[0]["label"] = "mutated"
    assert tq.get_template("gbc")["custom_questions"][0]["label"] != "mutated"
