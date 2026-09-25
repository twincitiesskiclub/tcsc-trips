import json

import pytest

from app.analytics.corrections import (
    CorrectionError, export_corrections, import_corrections, load_corrections,
    upsert_correction, validate_correction)

KEY = "C042G463AQ1:4087911600.000100"


@pytest.mark.parametrize("fields", [
    {"create": True, "date": "2099-07-17"},
    {"create": False},
    {"create": True, "date": "2099-07-17", "start_time": "07:00",
     "location": "Test studio", "activities": ["Strength"], "types": ["Circuit"],
     "kind": "practice", "status": "held", "rsvp_emoji": ["white_check_mark"],
     "plan_emoji": ["book"]},
])
def test_create_validation_accepts_post_key(fields):
    assert validate_correction(KEY, fields) == fields


@pytest.mark.parametrize("fields,match", [
    ({"create": True}, "date"),
    ({"create": True, "date": None}, "date"),
    ({"create": True, "date": "2099-02-30"}, "date"),
    ({"create": "true", "date": "2099-07-17"}, "create"),
    ({"create": 1, "date": "2099-07-17"}, "create"),
    ({"create": None}, "create"),
])
def test_create_validation_rejects_invalid_fields(fields, match):
    with pytest.raises(CorrectionError, match=match):
        validate_correction(KEY, fields)


@pytest.mark.parametrize("key", [KEY + ":main", KEY + ":early", KEY + ":late",
    KEY + ":merged", KEY + ":2099-07-17", "practice:123"])
@pytest.mark.parametrize("create", [True, False])
def test_create_validation_requires_post_key(key, create):
    with pytest.raises(CorrectionError, match="create"):
        validate_correction(key, {"create": create, "date": "2099-07-17"})


@pytest.mark.parametrize("key,fields", [
    ("not-a-key", {"skip": True}),
    (KEY, {}),
    (KEY, {"merged": "yes"}),
    (KEY, {"status": "gone"}),
    (KEY, {"add": [{"slack_uid": "UFAKE1", "role": "boss"}]}),
    (KEY, {"unknown_field": 1}),
])
def test_validation_rejects(key, fields):
    with pytest.raises(CorrectionError):
        validate_correction(key, fields)


def test_upsert_requires_note_and_round_trips(db_session, tmp_path):
    with pytest.raises(CorrectionError):
        upsert_correction(KEY, {"merged": True}, "", "test")
    upsert_correction(KEY, {"merged": True}, "thread says merged", "test")
    upsert_correction(KEY + ":early", {"ok": True}, "checked", "test")
    db_session.flush()
    assert load_corrections()[KEY] == {"merged": True}
    out = tmp_path / "c.json"
    export_corrections(out)
    data = json.loads(out.read_text())
    assert data[KEY] == {"fields": {"merged": True}, "note": "thread says merged", "author": "test"}


def test_import_validates_everything_before_writing(db_session, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "practice:1": {"fields": {"skip": True}, "note": "dup post"},
        "practice:2": {"fields": {"skip": "nope"}, "note": "bad"}}))
    with pytest.raises(CorrectionError):
        import_corrections(bad)
    assert "practice:1" not in load_corrections()


@pytest.mark.parametrize("fields", [
    {"skip": 1}, {"ok": None}, {"kind": "training"}, {"kind": []},
    {"date": "2099-02-30"}, {"date": "20990716"},
    {"start_time": "6:05"}, {"start_time": "24:00"},
    {"rsvp_emoji": "six"}, {"plan_emoji": [1]}, {"activities": [None]},
    {"types": {}}, {"location": 1}, {"rsvp_from": [KEY + ":early"]},
    {"add": ["UFAKE1"]}, {"remove": [{"role": "rsvp"}]},
    {"add": [{"slack_uid": 1, "role": "lead"}]},
])
def test_validation_checks_field_types(fields):
    with pytest.raises(CorrectionError):
        validate_correction(KEY, fields)


@pytest.mark.parametrize("key", [KEY, KEY + ":early", KEY + ":late",
    KEY + ":merged", KEY + ":main", KEY + ":2099-07-16", "practice:123"])
def test_validation_accepts_all_fields_and_key_forms(key):
    fields = {"skip": False, "merged": True, "ok": True, "kind": "event",
              "status": "cancelled", "date": "2099-07-16", "start_time": "06:05",
              "rsvp_emoji": ["six"], "plan_emoji": ["ski"],
              "activities": ["Strength"], "types": ["Circuit"],
              "location": "Test studio", "rsvp_from": [KEY],
              "add": [{"slack_uid": "UFAKE1", "role": "lead"}],
              "remove": [{"slack_uid": "UFAKE2", "role": "coach"}]}
    assert validate_correction(key, fields) == fields


def test_import_export_update_and_default_author(db_session, tmp_path):
    path = tmp_path / "corrections.json"
    path.write_text(json.dumps({
        KEY: {"fields": {"ok": True}, "note": "checked"},
        KEY + ":early": {"fields": {"skip": True}, "note": "duplicate", "author": "test"},
    }))
    assert import_corrections(path) == 2
    row = upsert_correction(KEY, {"merged": False}, "two sessions", "test")
    assert row.fields == {"merged": False}
    count = export_corrections(path)
    data = json.loads(path.read_text())
    assert count == len(data)
    assert list(data) == sorted(data)
    assert data[KEY]["note"] == "two sessions"
    assert data[KEY + ":early"]["author"] == "test"
    path.write_text(json.dumps({KEY: {"fields": {"ok": True}, "note": "checked"}}))
    import_corrections(path)
    export_corrections(path)
    assert json.loads(path.read_text())[KEY]["author"] == "claude-fixer"


@pytest.mark.parametrize("entry", [None, {}, {"fields": {"ok": True}, "note": " "},
    {"fields": {"ok": True}, "note": "checked", "author": None}])
def test_import_bad_entry_does_not_update_existing(db_session, tmp_path, entry):
    upsert_correction(KEY, {"merged": False}, "original", "test")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({KEY: {"fields": {"merged": True}, "note": "changed"},
                                KEY + ":early": entry}))
    with pytest.raises(CorrectionError):
        import_corrections(path)
    assert load_corrections()[KEY] == {"merged": False}


@pytest.mark.parametrize("field", ["add", "remove"])
@pytest.mark.parametrize("uid", ["", "U", "U1", "XFAKE0001", "ufake0001", "UFAKE-1", " UFAKE0001",
                                  "UFAKE0001 ", "UFAKE0001\n", "U" + "A" * 20, None, 42])
def test_attendance_corrections_reject_invalid_slack_uid(field, uid):
    with pytest.raises(CorrectionError, match=field):
        validate_correction("practice:999", {field: [{"slack_uid": uid, "role": "rsvp"}]})


@pytest.mark.parametrize("field", ["add", "remove"])
@pytest.mark.parametrize("uid", ["U12", "W12", "UFAKE0001", "WFAKE0001", "U" + "A" * 19, "W" + "A" * 19])
def test_attendance_corrections_accept_slack_uid_boundaries(field, uid):
    fields = {field: [{"slack_uid": uid, "role": "rsvp"}]}
    assert validate_correction("practice:999", fields) == fields
