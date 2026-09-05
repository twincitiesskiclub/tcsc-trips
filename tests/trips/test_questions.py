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
                     "sisu", "birkie", "gbc", "hayward", "north_shore", "blank"):
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


@pytest.mark.parametrize("builtin", tq.BUILTIN_QUESTIONS)
def test_builtin_defaults_validate(builtin):
    tq.validate_questions([tq.expand_builtin({"builtin": builtin})])


def test_expand_carpool_includes_independent_followup_defaults():
    question = tq.expand_builtin({"builtin": "carpool"})
    assert question["followups"] == {
        "seats": {"label": "How many people can you accommodate (besides yourself)?",
                  "help_text": "", "enabled": True},
        "bikes": {"label": "How many bikes can you accommodate?", "help_text": "", "enabled": True},
        "hitch": {"label": "Do you have a trailer hitch?", "help_text": "", "enabled": True},
    }
    question["followups"]["seats"]["label"] = "Passenger seats?"
    assert tq.BUILTIN_QUESTIONS["carpool"]["followups"]["seats"]["label"] != "Passenger seats?"


def test_expand_builtin_merges_partial_followup_overrides():
    question = tq.expand_builtin({"builtin": "carpool", "followups": {
        "seats": {"label": "Passenger seats?"}, "bikes": {"enabled": False},
    }})
    tq.validate_questions([question])
    assert question["followups"]["seats"] == {
        "label": "Passenger seats?", "help_text": "", "enabled": True}
    assert question["followups"]["bikes"]["enabled"] is False
    assert question["followups"]["hitch"] == tq.BUILTIN_QUESTIONS["carpool"]["followups"]["hitch"]


@pytest.mark.parametrize("builtin", ["carpool", "dietary"])
def test_followups_are_required_in_stored_questions(builtin):
    question = tq.expand_builtin({"builtin": builtin})
    del question["followups"]
    with pytest.raises(ValueError, match="followups must be a mapping"):
        tq.validate_questions([question])


@pytest.mark.parametrize("builtin", ["carpool", "dietary"])
@pytest.mark.parametrize("change", ["unknown", "missing"])
def test_followup_keys_are_fixed(builtin, change):
    question = tq.expand_builtin({"builtin": builtin})
    if change == "unknown":
        question["followups"]["extra"] = {"label": "More?", "help_text": ""}
    else:
        question["followups"].pop(next(iter(question["followups"])))
    with pytest.raises(ValueError, match="followups must contain exactly"):
        tq.validate_questions([question])


@pytest.mark.parametrize("fields, message", [
    ({"label": " ", "help_text": "", "enabled": True}, "label must be non-empty text"),
    ({"label": 1, "help_text": "", "enabled": True}, "label must be non-empty text"),
    ({"label": "Seats?", "help_text": None, "enabled": True}, "help_text must be text"),
    ({"label": "Seats?", "help_text": "", "enabled": "true"}, "enabled.*bool"),
    ({"label": "Seats?", "help_text": "", "enabled": 1}, "enabled.*bool"),
    ({"label": "Seats?", "enabled": True}, "must contain exactly"),
    ({"label": "Seats?", "help_text": ""}, "must contain exactly"),
    ({"label": "Seats?", "help_text": "", "enabled": True, "required": True}, "must contain exactly"),
    (None, "must be a mapping"),
])
def test_followup_fields_are_validated(fields, message):
    question = tq.expand_builtin({"builtin": "carpool"})
    question["followups"]["seats"] = fields
    with pytest.raises(ValueError, match=message):
        tq.validate_questions([question])


def test_dietary_other_cannot_be_disabled():
    question = tq.expand_builtin({"builtin": "dietary"})
    question["followups"]["other"]["enabled"] = False
    with pytest.raises(ValueError, match="must contain exactly help_text, label"):
        tq.validate_questions([question])


@pytest.mark.parametrize("builtin", ["tent", "region_code"])
def test_other_builtins_reject_followups(builtin):
    question = tq.expand_builtin({"builtin": builtin}) | {"followups": {}}
    with pytest.raises(ValueError, match="unsupported fields: followups"):
        tq.validate_questions([question])


@pytest.mark.parametrize("overrides, message", [
    ({"builtin": "unknown"}, "unknown built-in"),
    ({"builtin": []}, "unknown built-in"),
    ({"required": "true"}, "required.*bool"),
    ({"enabled": 1}, "enabled.*bool"),
    ({"enabled": None}, "enabled.*bool"),
    ({"label": " "}, "label"),
    ({"help_text": []}, "help_text"),
    ({"key": "can_drive"}, "fixed"),
    ({"type": "text"}, "fixed"),
    ({"visible_if": {"question": "chore", "equals": "yes"}}, "fixed"),
    ({"options": ["yes", "no"]}, "fixed"),
])
def test_builtin_schema_rejects_invalid_fields(overrides, message):
    question = tq.expand_builtin({"builtin": "carpool"}) | overrides
    with pytest.raises(ValueError, match=message):
        tq.validate_questions([question])


def test_builtin_dupes_rejected_even_when_disabled():
    question = tq.expand_builtin({"builtin": "carpool"})
    with pytest.raises(ValueError, match="duplicated"):
        tq.validate_questions([question, _q(), question | {"enabled": False}])


@pytest.mark.parametrize("options", [
    [], "Vegan", ["Vegan"], [tq.DIETARY_OTHER, tq.DIETARY_OTHER],
    [tq.DIETARY_OTHER, "Vegan", "Vegan"], [tq.DIETARY_OTHER, ""],
    [tq.DIETARY_OTHER, "  "], [tq.DIETARY_OTHER, " Vegan"],
    [tq.DIETARY_OTHER, None], [tq.DIETARY_OTHER, {}],
])
def test_dietary_options_schema(options):
    with pytest.raises(ValueError, match="dietary options"):
        tq.validate_questions([tq.expand_builtin({"builtin": "dietary", "options": options})])


def test_dietary_custom_options_and_sentinel_at_any_position():
    tq.validate_questions([tq.expand_builtin({"builtin": "dietary", "options": [
        tq.DIETARY_OTHER, "No restrictions", "Sesame allergy",
    ]})])


def test_builtin_cannot_be_a_custom_visibility_parent():
    with pytest.raises(ValueError, match="earlier"):
        tq.validate_questions([tq.expand_builtin({"builtin": "tent"}),
                               _q(visible_if={"question": "tent", "equals": "yes"})])


def test_every_template_expands_builtins_first_without_changing_custom_order():
    templates = tq.load_trip_templates()
    for template in templates.values():
        assert template["custom_questions"][:4] == tq.default_builtin_questions()
        assert all("builtin" not in q for q in template["custom_questions"][4:])
    assert templates["blank"]["custom_questions"] == tq.default_builtin_questions()
    assert [q["key"] for q in templates["north_shore"]["custom_questions"][4:]] == [
        "departure_time", "chore_preference", "bed_share", "room_share", "activities"]


def test_template_loader_expands_overrides_in_place(tmp_path, monkeypatch):
    config = tmp_path / "templates.yaml"
    config.write_text("""templates:
  mixed:
    name: Mixed
    custom_questions:
      - {key: note, label: Note, type: text, required: false}
      - {builtin: region_code, label: Home region, required: false}
      - {builtin: dietary, enabled: false, options: [Sesame allergy, Other (specify below)]}
""")
    monkeypatch.setattr(tq, "_CONFIG_PATH", config)
    monkeypatch.setattr(tq, "_template_cache", None)
    questions = tq.load_trip_templates()["mixed"]["custom_questions"]
    assert questions[0]["key"] == "note"
    assert questions[1] == tq.BUILTIN_QUESTIONS["region_code"] | {
        "label": "Home region", "required": False}
    assert questions[2]["enabled"] is False
    assert questions[2]["options"] == ["Sesame allergy", tq.DIETARY_OTHER]
    assert tq.BUILTIN_QUESTIONS["region_code"]["required"] is True
