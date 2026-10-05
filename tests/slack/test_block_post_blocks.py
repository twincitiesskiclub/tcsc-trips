import json
from datetime import date, datetime
from types import SimpleNamespace

from app.slack.blocks.block_post import block_range_label, build_block_post


def _poll(status="draft", message_ts=None, opened_by=None, closed_at=None, pid=7,
          opened_at=None):
    return SimpleNamespace(id=pid, starts_on=date(2099, 1, 19), ends_on=date(2099, 2, 1),
                           status=status, message_ts=message_ts,
                           opened_by_slack_uid=opened_by, opened_at=opened_at,
                           closed_at=closed_at)


def _row(pid, *, emoji="letter_a", where="TEST Wirth · Bounding", leads=(), coaches=(),
         needed=2, available=0, cancelled=False, day=20):
    return {"practice_id": pid, "emoji": emoji, "when": datetime(2099, 1, day, 18, 15),
            "where": where, "cancelled": cancelled, "leads": list(leads),
            "coaches": list(coaches), "leads_needed": needed, "available": available}


def _text(blocks):
    return json.dumps(blocks, ensure_ascii=False)


def test_range_label():
    assert block_range_label(date(2026, 10, 26), date(2026, 11, 8)) == "Oct 26 – Nov 8"


def test_before_opening_lists_sessions_with_open_and_edit():
    blocks = build_block_post(_poll(), [_row(1), _row(2, where="location TBD", day=22)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Lead poll · Jan 19 – Feb 1" in text
    assert "location TBD" in text
    assert '"action_id": "block_poll_open"' in text
    assert '"action_id": "edit_practice_full"' in text
    assert "<#C02J4DGCFL2>" in text
    assert "Assign" not in text
    assert "—" not in text


def test_before_opening_omits_cancelled_sessions():
    blocks = build_block_post(_poll(), [_row(1), _row(2, cancelled=True, day=22)],
                              permalink=None, footer=None)
    assert "Thu 1/22" not in _text(blocks)


def test_open_rows_have_dot_letter_leads_and_assign():
    rows = [
        _row(1, leads=["Katrin S"], available=2),                       # yellow, needs 1 more
        _row(2, emoji="letter_b", leads=["Ellie T", "Jacob D"], day=22),  # green
        _row(3, emoji="letter_c", day=22),                              # red
    ]
    blocks = build_block_post(_poll("open", "2.0", "U0CHRIS"), rows,
                              permalink="https://x/p", footer="31 of 60 leads have answered.")
    text = _text(blocks)
    assert "Opened by <@U0CHRIS>" in text and "<https://x/p|see the poll>" in text
    assert ":large_yellow_circle: :letter_a:" in text
    assert "Leads: Katrin S · needs 1 more" in text
    assert ":large_green_circle: :letter_b:" in text
    assert ":red_circle: :letter_c:" in text and "No leads yet" in text
    assert text.count('"action_id": "block_assign"') == 3
    assert "31 of 60 leads have answered." in text
    assert "block_poll_open" not in text


def test_coaches_are_shown_not_counted():
    blocks = build_block_post(_poll("open", "2.0"), [_row(1, coaches=["KJ"])],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Coach: KJ · No leads yet" in text
    assert ":red_circle:" in text


def test_leads_needed_one_and_three():
    one = _text(build_block_post(_poll("open", "2.0"), [_row(1, leads=["A B"], needed=1)],
                                 permalink=None, footer=None))
    three = _text(build_block_post(_poll("open", "2.0"), [_row(1, leads=["A B"], needed=3)],
                                   permalink=None, footer=None))
    assert ":large_green_circle:" in one and "needs" not in one
    assert "needs 2 more" in three


def test_cancelled_after_opening_is_struck_through_without_assign():
    blocks = build_block_post(_poll("open", "2.0"), [_row(1, cancelled=True)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "~" in text and "Cancelled" in text
    assert "block_assign" not in text


def test_closed_drops_footer_keeps_assign():
    blocks = build_block_post(_poll("closed", "2.0", closed_at=datetime(2099, 2, 2, 8, 30)),
                              [_row(1)], permalink=None, footer=None)
    text = _text(blocks)
    assert "Poll closed Mon 2/2" in text
    assert "block_assign" in text


def test_never_posted_block_reads_collected_outside_the_app():
    blocks = build_block_post(_poll("closed", None), [_row(1, emoji=None)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Availability collected outside the app" in text
    assert ":letter_" not in text
    assert "block_assign" in text


from app.slack.blocks.block_post import build_assign_modal


def _data(**over):
    data = {"practice_id": 5, "title": "Assign leads · Tue 10/27",
            "detail": "6:15p · TEST Wirth · Bounding · needs 2",
            "available_text": "Available: Katrin S, Micah R",
            "available": [(1, "Katrin S"), (2, "Micah R")],
            "others": [(3, "Augie L")], "initial_ids": [1]}
    data.update(over)
    return data


def test_assign_modal_shows_available_line_and_grouped_dropdown():
    view = build_assign_modal(_data())
    text = json.dumps(view)
    assert view["callback_id"] == "block_assign_submit"
    assert view["private_metadata"] == "5"
    assert "Available: Katrin S, Micah R" in text
    select = view["blocks"][-1]["element"]
    assert [g["label"]["text"] for g in select["option_groups"]] == ["Available", "Everyone else"]
    assert select["initial_options"][0]["value"] == "1"
    assert "max_selected_items" not in select


def test_assign_modal_with_no_poll_has_no_available_line_and_skips_empty_group():
    view = build_assign_modal(_data(available_text=None, available=[], initial_ids=[]))
    select = view["blocks"][-1]["element"]
    assert [g["label"]["text"] for g in select["option_groups"]] == ["Everyone else"]
    assert "initial_options" not in select
    assert "Available:" not in json.dumps(view)


def test_assign_modal_caps_options_and_initial_options_match_groups():
    others = [(100 + i, f"Person {i}") for i in range(150)]
    view = build_assign_modal(_data(others=others, initial_ids=[1, 100, 249]))
    select = view["blocks"][-1]["element"]
    shown = [o for g in select["option_groups"] for o in g["options"]]
    assert len(shown) == 100
    assert all(o in shown for o in select["initial_options"])
    assert [o["value"] for o in select["initial_options"]] == ["1", "100"]


def test_status_line_includes_the_open_date():
    from datetime import datetime
    opened = datetime(2099, 1, 12, 9, 0)  # a Monday
    with_uid = build_block_post(_poll("open", "2.0", "U0CHRIS", opened_at=opened), [_row(1)],
                                permalink="https://x/p", footer=None)
    assert "Opened by <@U0CHRIS>, Mon 1/12 · <https://x/p|see the poll>" in _text(with_uid)
    no_uid = build_block_post(_poll("open", "2.0", opened_at=opened), [_row(1)],
                              permalink="https://x/p", footer=None)
    assert "Opened Mon 1/12 · <https://x/p|see the poll>" in _text(no_uid)
