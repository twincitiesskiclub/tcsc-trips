import json
from datetime import date, datetime
from types import SimpleNamespace

from app.slack.blocks.block_post import (
    block_range_label,
    build_block_post,
    build_lead_schedule,
    lead_schedule_text,
)


def _poll(status="draft", message_ts=None, opened_by=None, closed_at=None, pid=7,
          opened_at=None, schedule_ts=None):
    return SimpleNamespace(id=pid, starts_on=date(2099, 1, 19), ends_on=date(2099, 2, 1),
                           status=status, message_ts=message_ts,
                           opened_by_slack_uid=opened_by, opened_at=opened_at,
                           closed_at=closed_at, schedule_ts=schedule_ts)


def _row(pid, *, emoji="letter_a", where="TEST Wirth · Bounding", leads=(), coaches=(),
         needed=2, available=0, cancelled=False, day=20, mentions=None,
         activity="Pole Run", location="default", kinds=("Intervals",), hour=18):
    if location == "default":
        location = {"name": "TEST Wirth", "spot": "Xerxes Field", "url": "https://maps.example/w"}
    return {"practice_id": pid, "emoji": emoji, "when": datetime(2099, 1, day, hour, 15),
            "where": where, "cancelled": cancelled, "leads": list(leads),
            "lead_mentions": list(leads if mentions is None else mentions),
            "coaches": list(coaches), "leads_needed": needed, "available": available,
            "activity": activity, "location": location, "kinds": list(kinds)}


NOW = datetime(2099, 1, 1, 9, 0)  # before every test session


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


def _by_id(view):
    return {b["block_id"]: b for b in view["blocks"] if b.get("block_id")}


def test_assign_modal_has_prefilled_location_type_and_activity():
    view = build_assign_modal(
        _data(location_id=2, type_ids=[11], activity_ids=[21, 22]),
        locations=[(1, "Wirth - Chalet"), (2, "Hyland")],
        all_types=[(10, "Intervals"), (11, "Distance")],
        all_activities=[(21, "Classic"), (22, "Skate"), (23, "Run")])
    blocks = _by_id(view)
    assert list(blocks) == ["leads", "location", "types", "activities"]
    loc = blocks["location"]["element"]
    assert loc["type"] == "static_select" and loc["action_id"] == "location_select"
    assert loc["initial_option"]["value"] == "2"
    assert blocks["location"]["optional"] is True
    types = blocks["types"]["element"]
    assert types["action_id"] == "type_ids"
    assert [o["value"] for o in types["initial_options"]] == ["11"]
    acts = blocks["activities"]["element"]
    assert acts["action_id"] == "activity_ids"
    assert [o["value"] for o in acts["initial_options"]] == ["21", "22"]


def test_assign_modal_omits_location_without_locations_and_keeps_available_above_leads():
    view = build_assign_modal(_data(), all_types=[(10, "Intervals")])
    blocks = _by_id(view)
    assert "location" not in blocks and "types" in blocks
    kinds = [b["type"] for b in view["blocks"]]
    assert kinds.index("section") < view["blocks"].index(blocks["leads"])
    assert "initial_option\"" not in json.dumps(view)


def test_schedule_button_on_open_and_closed_polls_until_posted():
    for poll in (_poll("open", "2.0"), _poll("closed", None)):
        text = _text(build_block_post(poll, [_row(1)], permalink=None, footer=None))
        assert '"action_id": "block_schedule_post"' in text
        assert '"confirm"' in text
    draft = _text(build_block_post(_poll(), [_row(1)], permalink=None, footer=None))
    assert "block_schedule_post" not in draft


def test_posted_schedule_replaces_the_button_with_a_channel_link():
    text = _text(build_block_post(_poll("open", "2.0", schedule_ts="5.0"), [_row(1)],
                                  permalink=None, footer=None))
    assert "block_schedule_post" not in text
    assert "Schedule posted to <#C02J4DGCFL2>" in text


def test_lead_schedule_groups_weeks_in_one_quote_each():
    rows = [
        _row(1, leads=["Katrin O", "Gunnar M"], mentions=["<@U1>", "<@U2>"]),
        _row(2, leads=["Jo E", "Al B"], mentions=["<@U3>", "<@U4>"], day=22),
        _row(3, leads=["Mo P", "Di Q"], mentions=["<@U5>", "<@U6>"], day=27),
    ]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    assert blocks[0]["text"]["text"] == ":ski: Lead schedule · Jan 19 – Feb 1"
    sections = [b for b in blocks if b["type"] == "section"]
    assert len(sections) == 2
    week1 = sections[0]["text"]["text"]
    assert week1.startswith("*Week of Jan 19*\n> :runner:  *Tue 1/20* · 6:15p · "
                            "<https://maps.example/w|TEST Wirth, Xerxes Field> · Intervals\n"
                            "> <@U1> and <@U2>\n>\n> :runner:  *Thu 1/22*")
    assert sections[1]["text"]["text"].startswith("*Week of Jan 26*\n")
    assert not any(b["type"] in ("actions", "divider") for b in blocks)
    assert blocks[-1] == {"type": "context", "elements": [{"type": "mrkdwn", "text":
        "Can't make yours? Ask in this thread for a sub."}]}
    assert "—" not in _text(blocks)


def test_lead_schedule_needs_lines_coaches_and_place_fallbacks():
    rows = [
        _row(1, location=None, kinds=()),
        _row(2, leads=["Joe H"], mentions=["<@U3>"], coaches=["KJ"], day=22),
        _row(3, needed=1, day=27),
        _row(4, location={"name": "TEST Balance", "spot": None, "url": None},
             activity="Strength", kinds=("Circuit",), day=29),
    ]
    text = _text(build_lead_schedule(_poll("closed"), rows, now=NOW))
    assert "*Tue 1/20* · 6:15p · location TBD\\n> :raising_hand: *Needs 2 leads*" in text
    assert "> <@U3> · :raising_hand: *Needs 1 more* · coach KJ" in text
    assert ":raising_hand: *Needs 1 lead*" in text
    assert ":muscle:  *Thu 1/29* · 6:15p · TEST Balance · Circuit" in text


def test_lead_schedule_escapes_names_and_keeps_links_intact():
    rows = [_row(1, location={"name": "TEST A&B <Park>", "spot": "Lot|2", "url": "https://m/x"},
                 kinds=("Run & Gun",))]
    text = build_lead_schedule(_poll("closed"), rows, now=NOW)[1]["text"]["text"]
    assert "<https://m/x|TEST A&amp;B &lt;Park&gt;, Lot 2>" in text
    assert "· Run &amp; Gun" in text


def test_cancelled_row_is_plain_strikethrough_without_button():
    rows = [_row(1, cancelled=True)]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    assert "> ~Tue 1/20 · 6:15p · TEST Wirth~ _Cancelled_" in blocks[1]["text"]["text"]
    assert not any(b["type"] == "actions" for b in blocks)


def test_activity_emoji_keywords_and_fallback():
    from app.slack.blocks.block_post import activity_emoji
    assert activity_emoji("Strength") == ":muscle:"
    assert activity_emoji("Mountain Bike") == ":bicyclist:"
    assert activity_emoji("Skate/Classic Rollerski") == ":ski:"
    assert activity_emoji("Pole Hike, Pole Run") == ":runner:"
    assert activity_emoji("Hike") == ":runner:"
    assert activity_emoji("Orienteering") == ":ski:"
    assert activity_emoji(None) == ":ski:"


def test_lead_buttons_only_for_takeable_sessions_with_unique_ids():
    rows = [
        _row(1),                                              # open
        _row(2, leads=["Sarah H"], mentions=["<@U9>"], hour=19),  # partial, same day
        _row(3, leads=["A B", "C D"], mentions=["<@U1>", "<@U2>"], day=22),  # full
        _row(4, cancelled=True, day=22, hour=19),             # cancelled
    ]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    buttons = actions[0]["elements"]
    assert [b["action_id"] for b in buttons] == ["lead_signup_1", "lead_signup_2"]
    assert [b["value"] for b in buttons] == ["1", "2"]
    assert buttons[0]["text"]["text"] == "Lead Tue 1/20 · 6:15p"
    confirm = buttons[0]["confirm"]
    assert confirm["title"]["text"] == "Lead this practice?"
    assert confirm["confirm"]["text"] == "I'll lead it"
    assert confirm["deny"]["text"] == "Cancel"
    assert confirm["text"]["text"] == (
        "Tue 1/20 at 6:15p, Intervals at TEST Wirth. "
        "You're added right away. If plans change, ask in the thread.")
    assert "You'll lead with Sarah H." in buttons[1]["confirm"]["text"]["text"]
    assert all(len(b["confirm"]["text"]["text"]) <= 300 for b in buttons)


def test_past_sessions_get_no_button_and_do_not_count_as_open():
    from app.slack.blocks.block_post import lead_schedule_text
    rows = [_row(1), _row(2, day=27)]
    later = datetime(2099, 1, 21, 9, 0)  # after 1/20, before 1/27
    blocks = build_lead_schedule(_poll("closed"), rows, now=later)
    buttons = [e for b in blocks if b["type"] == "actions" for e in b["elements"]]
    assert [b["action_id"] for b in buttons] == ["lead_signup_2"]
    assert lead_schedule_text(_poll("closed"), rows, now=later).endswith(
        "· 1 practice still needs leads")


def test_star_line_wording():
    def footer(rows):
        return build_lead_schedule(_poll("closed"), rows, now=NOW)[-1]["elements"][0]["text"]

    full = lambda pid, a, b, **kw: _row(pid, leads=["x", "y"], mentions=[a, b], **kw)  # noqa: E731
    assert footer([full(1, "<@A>", "<@B>")]).startswith("Can't make yours?")
    assert footer([full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@C>", day=22)]).startswith(
        ":star: <@A> is leading twice.\n")
    assert footer([full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@B>", day=22)]).startswith(
        ":star: <@A> and <@B> are leading twice.\n")
    three = [full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@B>", day=22),
             full(3, "<@A>", "<@C>", day=27)]
    assert footer(three).startswith(
        ":star: <@B> is leading twice.\n:star: <@A> is leading 3 times.\n")


def test_cancelled_sessions_do_not_count_toward_stars():
    rows = [_row(1, leads=["x"], mentions=["<@A>"]),
            _row(2, leads=["x"], mentions=["<@A>"], cancelled=True, day=22)]
    footer = build_lead_schedule(_poll("closed"), rows, now=NOW)[-1]["elements"][0]["text"]
    assert ":star:" not in footer


def test_lead_schedule_text_plurals():
    from app.slack.blocks.block_post import lead_schedule_text
    full = _row(9, leads=["a", "b"], mentions=["<@A>", "<@B>"])
    poll = _poll("closed")
    assert lead_schedule_text(poll, [full], now=NOW) == (
        "Lead schedule for Jan 19 – Feb 1 is up · every practice has leads")
    assert lead_schedule_text(poll, [_row(1), full], now=NOW).endswith(
        "· 1 practice still needs leads")
    assert lead_schedule_text(poll, [_row(1), _row(2, day=22)], now=NOW).endswith(
        "· 2 practices still need leads")


def test_join_names():
    from app.slack.blocks.block_post import join_names
    assert join_names([]) == ""
    assert join_names(["a"]) == "a"
    assert join_names(["a", "b"]) == "a and b"
    assert join_names(["a", "b", "c"]) == "a, b and c"


def test_post_schedule_confirm_mentions_lead_buttons():
    text = _text(build_block_post(_poll("open", "2.0"), [_row(1)], permalink=None, footer=None))
    assert "Open sessions get a Lead button anyone in the lead pool can take." in text
