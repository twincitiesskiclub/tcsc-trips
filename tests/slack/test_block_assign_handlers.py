"""The Assign button opens the modal; submitting saves the chosen leads."""

from contextlib import nullcontext

from app.slack import bolt_app


def test_assign_submission_saves_selected_leads(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.save_assigned_leads",
                        lambda pid, ids: saved.append((pid, ids)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    view = {"private_metadata": "5", "state": {"values": {"leads": {"leads_select": {
        "selected_options": [{"value": "1"}, {"value": "3"}]}}}}}
    bolt_app._save_block_assign(view)
    assert saved == [(5, [1, 3])]


def test_assign_submission_with_nothing_selected_clears_leads(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.save_assigned_leads",
                        lambda pid, ids: saved.append((pid, ids)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    view = {"private_metadata": "5", "state": {"values": {"leads": {"leads_select": {}}}}}
    bolt_app._save_block_assign(view)
    assert saved == [(5, [])]
