"""The Assign button opens the modal; submitting saves leads, location, type and activity."""

from contextlib import nullcontext

from app.slack import bolt_app


def _view(values):
    return {"private_metadata": "5", "state": {"values": values}}


FULL = {
    "leads": {"leads_select": {"selected_options": [{"value": "1"}, {"value": "3"}]}},
    "location": {"location_select": {"selected_option": {"value": "7"}}},
    "types": {"type_ids": {"selected_options": [{"value": "11"}]}},
    "activities": {"activity_ids": {"selected_options": [{"value": "21"}, {"value": "22"}]}},
}


def test_valid_submission_saves_parsed_values(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.validate_assignment", lambda t, a: None)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append((pid, kw)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    assert bolt_app._save_block_assign(_view(FULL)) is None
    assert saved == [(5, {"lead_ids": [1, 3], "location_id": 7,
                          "type_ids": [11], "activity_ids": [21, 22],
                          "initial_lead_ids": None})]


def test_empty_submission_parses_to_empty_and_none(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.validate_assignment", lambda t, a: None)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append((pid, kw)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    bolt_app._save_block_assign(_view({"leads": {"leads_select": {}}}))
    assert saved == [(5, {"lead_ids": [], "location_id": None,
                          "type_ids": [], "activity_ids": [],
                          "initial_lead_ids": None})]


def test_validation_error_acks_with_errors_and_does_not_save(monkeypatch, app):
    saved, acks = [], []
    monkeypatch.setattr("app.practices.blocks.validate_assignment",
                        lambda t, a: ("types", "Conflicting reactions"))
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append(kw))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    bolt_app._save_block_assign(_view(FULL), lambda **kw: acks.append(kw))
    assert acks == [{"response_action": "errors", "errors": {"types": "Conflicting reactions"}}]
    assert saved == []


def test_valid_submit_acks_then_saves(monkeypatch, app):
    order = []
    monkeypatch.setattr("app.practices.blocks.validate_assignment", lambda t, a: None)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: order.append("save"))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    bolt_app._save_block_assign(_view(FULL), lambda **kw: order.append("ack"))
    assert order == ["ack", "save"]


def test_validation_crash_acks_with_errors_and_does_not_save(monkeypatch, app):
    saved, acks = [], []

    def boom(t, a):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.practices.blocks.validate_assignment", boom)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append(kw))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    with app.app_context():
        bolt_app._save_block_assign(_view(FULL), lambda **kw: acks.append(kw))
    assert len(acks) == 1 and acks[0]["response_action"] == "errors"
    assert "leads" in acks[0]["errors"]
    assert saved == []


def test_json_metadata_passes_the_opening_leads(monkeypatch, app):
    import json

    saved = []
    monkeypatch.setattr("app.practices.blocks.validate_assignment", lambda t, a: None)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append((pid, kw)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    view = {"private_metadata": json.dumps({"practice_id": 5, "initial_lead_ids": [1, 2]}),
            "state": {"values": FULL}}
    bolt_app._save_block_assign(view)
    assert saved[0][0] == 5
    assert saved[0][1]["initial_lead_ids"] == [1, 2]
