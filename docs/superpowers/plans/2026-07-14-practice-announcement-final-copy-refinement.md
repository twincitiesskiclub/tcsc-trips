# Practice Announcement Final Copy Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compact RSVP guidance onto one line whenever no supplemental emoji exists, and replace the standalone Where: label with the approved Where · location - spot heading.

**Architecture:** Keep the existing shared _rsvp_context_block() boundary and choose its separator from the already-rendered supplemental sentence. Change only the standalone location-line composition; models, reactions, fallbacks, and Block Kit structure stay intact. Refresh one synthetic combined fixture so guarded Slack review visibly covers both RSVP layouts.

**Tech Stack:** Python 3.13, pytest, Slack Block Kit, slack_sdk, existing announcement builders, and the guarded Slack harness.

## Global Constraints

- RSVP remains one context block containing one mrkdwn element.
- No supplemental reaction sentence means no manual newline before Running late?.
- A supplemental reaction sentence means exactly one manual newline before Running late?.
- Apply the same conditional rule to standalone and combined roots.
- Preserve the exact tail: Running late? Reply in the thread. <!channel>.
- The location first line is fully bold and shaped as *Where · {location}[ - {spot}]*.
- Preserve the address line, map pin, ASCII hyphen, fallbacks, and stored data.
- Do not change models, schema, settings, authoring UI, reaction lifecycle, Details replies, or weekly summaries.
- Use strict RED-GREEN TDD for each behavior change.
- Never post outside C07G9RTMRT3 and never expose secrets.
- Preserve the intentional untracked env symlink.
- Retain a successful final harness run for product-owner sign-off.

---

### Task 1: Make RSVP wrapping conditional in the shared formatter

**Files:**
- Modify: app/slack/blocks/announcements.py:88-115
- Test: tests/slack/test_announcement_blocks.py:415-494
- Test: tests/slack/test_combined_announcements.py:98-146

**Interfaces:**
- Consumes: format_supplemental_reaction_sentence(reactions) -> str and _RUNNING_LATE_LINE.
- Produces: unchanged _rsvp_context_block(attendance_sentence, reactions, *, surface, practice_id=None) -> dict, with zero or one newline based on the rendered supplemental sentence.

- [ ] **Step 1: Specify standalone conditional wrapping**

Keep the existing parametrization, rename the test, and replace its body with:

    def test_standalone_rsvp_uses_conditional_line_break(
        practice_info, conditions, reactions, supplemental
    ):
        practice_info.plan_reactions = reactions
        block = _rsvp_context(
            build_practice_announcement_blocks(practice_info, conditions)
        )
        separator = "\n" if supplemental else " "
        assert block["elements"] == [{
            "type": "mrkdwn",
            "text": (
                "Bop :white_check_mark: so we'll know you'll be there."
                f"{supplemental}{separator}"
                "Running late? Reply in the thread. <!channel>"
            ),
        }]
        assert len(block["elements"][0]["text"].splitlines()) == (
            2 if supplemental else 1
        )

Leave the long-supplement budget test at two lines; its monkeypatch returns a non-empty supplemental sentence.

- [ ] **Step 2: Specify combined wrapping**

Change the no-plan cross-day expectation to:

    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM "
        "so we'll know you'll be there. Running late? Reply in the thread. "
        "<!channel>"
    )
    assert len(_combined_rsvp_text(blocks).splitlines()) == 1

Change the no-plan same-day expectation to:

    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for 6:05 PM or :seven: for 7:20 PM "
        "so we'll know you'll be there. Running late? Reply in the thread. "
        "<!channel>"
    )
    assert len(_combined_rsvp_text(blocks).splitlines()) == 1

Keep the shared-plan expected text unchanged and add:

    rsvp = _combined_rsvp_text(build_combined_lift_blocks(practices))
    assert len(rsvp.splitlines()) == 2

- [ ] **Step 3: Verify RED**

Run:

    env/bin/pytest -q \
      tests/slack/test_announcement_blocks.py::test_standalone_rsvp_uses_conditional_line_break \
      tests/slack/test_combined_announcements.py::test_cross_day_mapping_is_only_in_bottom_context \
      tests/slack/test_combined_announcements.py::test_combined_shared_plan_is_appended_to_attendance_line \
      tests/slack/test_combined_announcements.py::test_same_day_rows_and_mapping_use_times_only

Expected: the empty standalone case and both no-plan combined cases fail because production still inserts a newline; supplemental cases pass.

- [ ] **Step 4: Implement the minimal separator change**

After first_line is assembled, replace the unconditional newline with:

    separator = "\n" if supplemental else " "
    return {
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"{first_line}{separator}{_RUNNING_LATE_LINE}",
        }],
    }

Do not add a surface branch. Newline and space are both one character, so the reserved-tail budget remains correct.

- [ ] **Step 5: Verify GREEN**

Run:

    env/bin/pytest -q \
      tests/slack/test_announcement_blocks.py \
      tests/slack/test_combined_announcements.py

Expected: PASS with the fallback assertions unchanged.

- [ ] **Step 6: Commit**

    git add app/slack/blocks/announcements.py \
      tests/slack/test_announcement_blocks.py \
      tests/slack/test_combined_announcements.py
    git commit -m "fix(slack): compact simple practice rsvp copy"

---

### Task 2: Apply the dot-separated location heading

**Files:**
- Modify: app/slack/blocks/announcements.py:325-338
- Test: tests/slack/test_announcement_blocks.py:157-189,882-893

**Interfaces:**
- Consumes: location name, optional spot, and _address_link(location).
- Produces: the same section block with first line *Where · {location}[ - {spot}]*; address behavior is unchanged.

- [ ] **Step 1: Specify the exact primary heading**

Change the urgent-order helper to search for "*Where ·" rather than "*Where:*".

Replace the hero test with:

    def test_hero_has_dot_separated_where_workout_notes_and_social(
        practice_info, conditions
    ):
        blocks = build_practice_announcement_blocks(practice_info, conditions)
        where = next(
            block["text"]["text"]
            for block in blocks
            if block.get("type") == "section"
            and block.get("text", {}).get("text", "").startswith("*Where")
        )
        assert where == (
            "*Where · Theodore Wirth - Trailhead*\n"
            "📍 <https://maps.example/wirth|1301 Theodore Wirth Pkwy>\n\u200b"
        )
        text = rendered_text(blocks)
        assert "*Where:*" not in text
        assert "*Workout · Intervals*" in text
        assert "*📝 Notes*" in text
        assert "Social after at Utepils Brewing" in text

Change the long-content required string from "*Where:*" to "*Where ·".

- [ ] **Step 2: Specify missing-value behavior**

Add:

    def test_where_heading_omits_absent_spot(practice_info, conditions):
        practice_info.location.spot = None
        text = rendered_text(
            build_practice_announcement_blocks(practice_info, conditions)
        )
        assert "*Where · Theodore Wirth*" in text
        assert "*Where · Theodore Wirth -*" not in text


    def test_where_heading_uses_tbd_without_location(practice_info, conditions):
        practice_info.location = None
        text = rendered_text(
            build_practice_announcement_blocks(practice_info, conditions)
        )
        assert "*Where · TBD*" in text
        assert "📍" not in text

- [ ] **Step 3: Verify RED**

Run:

    env/bin/pytest -q \
      tests/slack/test_announcement_blocks.py::test_hero_has_dot_separated_where_workout_notes_and_social \
      tests/slack/test_announcement_blocks.py::test_where_heading_omits_absent_spot \
      tests/slack/test_announcement_blocks.py::test_where_heading_uses_tbd_without_location

Expected: three failures because production still renders *Where:*.

- [ ] **Step 4: Implement the approved heading**

Replace the current where_text assignment with:

    location_label = location_name + (" - " + spot if spot else "")
    where_text = f"*Where · {location_label}*"

Leave _address_link() and the following map-pin line unchanged.

- [ ] **Step 5: Verify GREEN**

Run:

    env/bin/pytest -q tests/slack/test_announcement_blocks.py

Expected: PASS, including urgent-ordering, limits, fallbacks, and empty data.

- [ ] **Step 6: Commit**

    git add app/slack/blocks/announcements.py \
      tests/slack/test_announcement_blocks.py
    git commit -m "fix(slack): align practice location heading"

---

### Task 3: Make guarded review cover both RSVP layouts

**Files:**
- Modify: scripts/validate_announcement.py:288-306
- Test: tests/scripts/test_validate_announcement.py:168-210

**Interfaces:**
- Consumes: final public builders through build_scenario(name, scenario).
- Produces: the same 16-scenario registry; combined_strength keeps supplemental guidance and combined_strength_same_day becomes the combined no-supplement fixture.

- [ ] **Step 1: Add a real-block RSVP extractor**

Add near the harness test helpers:

    def _rsvp_text(blocks):
        matches = [
            element["text"]
            for block in blocks
            if block.get("type") == "context"
            for element in block.get("elements", [])
            if element.get("text", "").startswith("Bop ")
        ]
        assert len(matches) == 1
        return matches[0]

- [ ] **Step 2: Specify the review matrix**

Extend test_approved_review_scenarios_render_exact_copy_and_icons():

    routine = validate.SCENARIOS["routine"]
    routine_blocks, _, _ = validate.build_scenario("routine", routine)
    assert len(_rsvp_text(routine_blocks).splitlines()) == 1
    assert "*Where · Theodore Wirth - Trailhead*" in str(routine_blocks)

    assert len(_rsvp_text(standalone_blocks).splitlines()) == 2

    assert all(practice.plan_reactions for practice in cross_day.practices)
    assert len(_rsvp_text(cross_blocks).splitlines()) == 2

    assert all(not practice.plan_reactions for practice in same_day.practices)
    assert len(_rsvp_text(same_blocks).splitlines()) == 1

- [ ] **Step 3: Verify RED**

Run:

    env/bin/pytest -q \
      tests/scripts/test_validate_announcement.py::test_approved_review_scenarios_render_exact_copy_and_icons

Expected: FAIL because both same-day fixtures still use _combined_plan.

- [ ] **Step 4: Change only the same-day fixtures**

In _combined_same_day_early and _combined_same_day_late, replace:

    plan_reactions=_combined_plan,

with:

    plan_reactions=[],

Do not change the cross-day or mixed-cancellation fixtures.

- [ ] **Step 5: Verify GREEN**

Run:

    env/bin/pytest -q \
      tests/scripts/test_validate_announcement.py \
      tests/slack/test_announcement_blocks.py \
      tests/slack/test_combined_announcements.py

Expected: PASS. The registry remains 16 roots and 11 Details replies; same-day expected reactions no longer contain hatching_chick.

- [ ] **Step 6: Commit**

    git add scripts/validate_announcement.py \
      tests/scripts/test_validate_announcement.py
    git commit -m "test(slack): cover compact combined rsvp review"

---

### Task 4: Independently review, verify, and replace the Slack matrix

**Files:**
- Read: every file changed in 5931519..HEAD
- Retain ignored state: validate_posted_ts.json
- Update ignored ledger: .superpowers/sdd/progress.md

**Interfaces:**
- Consumes: committed builders and scripts.validate_announcement.main().
- Produces: a clean review, green suite, and retained test-channel run whose Slack-returned payloads match local output.

- [ ] **Step 1: Request independent review**

Use superpowers:requesting-code-review for 5931519..HEAD. Require the reviewer to check:

    - No supplemental sentence: one RSVP visual line on both surfaces.
    - Supplemental sentence: exactly two RSVP visual lines.
    - One context block and one mrkdwn element remain.
    - Location first line is exactly *Where · location - spot*.
    - Address, fallbacks, lifecycle, models, and unrelated surfaces are unchanged.
    - Real-builder tests and the harness cover both layouts.

Expected: no Critical or Important findings. Correct any valid finding with a failing regression first, then re-review.

- [ ] **Step 2: Run verification at the reviewed HEAD**

Run:

    env/bin/pytest -q \
      tests/scripts/test_validate_announcement.py \
      tests/slack/test_announcement_blocks.py \
      tests/slack/test_combined_announcements.py \
      tests/slack/test_details_reply_wiring.py
    env/bin/pytest -q tests
    env/bin/python -m py_compile \
      app/slack/blocks/announcements.py \
      scripts/validate_announcement.py
    git diff --check 5931519..HEAD
    git status --short

Expected: all tests pass, static checks are silent, and status contains only ?? env.

- [ ] **Step 3: Validate and remove the prior harness-owned run**

Preflight:

    env/bin/python - <<'PY'
    import json
    from pathlib import Path
    from scripts.validate_announcement import TEST_CHANNEL

    path = Path("validate_posted_ts.json")
    assert path.exists(), "expected retained review state"
    state = json.loads(path.read_text())
    assert state["records"]
    assert {record["channel"] for record in state["records"]} == {TEST_CHANNEL}
    assert len({record["ts"] for record in state["records"]}) == len(state["records"])
    print({"run_id": state["run_id"], "records": len(state["records"])})
    PY

Teardown:

    env/bin/python - <<'PY'
    from dotenv import load_dotenv
    load_dotenv('/Users/rob/env/tcsc-trips/.env', override=False)
    from scripts.validate_announcement import main
    raise SystemExit(main(['teardown']))
    PY
    test ! -e validate_posted_ts.json

Expected: exit zero and no state file. On failure, retain the state and retry; never edit or delete it manually.

- [ ] **Step 4: Post and validate the refreshed state**

Run:

    env/bin/python -u - <<'PY'
    from dotenv import load_dotenv
    load_dotenv('/Users/rob/env/tcsc-trips/.env', override=False)
    from scripts.validate_announcement import main
    raise SystemExit(main(['post']))
    PY

Poll any returned process handle through exit. Then run:

    env/bin/python - <<'PY'
    import json
    from collections import Counter
    from scripts.validate_announcement import TEST_CHANNEL

    state = json.load(open("validate_posted_ts.json"))
    assert len(state["records"]) == 27
    assert {record["channel"] for record in state["records"]} == {TEST_CHANNEL}
    assert Counter(
        "reply" if record.get("thread_ts") else "root"
        for record in state["records"]
    ) == {"root": 16, "reply": 11}
    assert not state.get("reaction_errors")
    print({"run_id": state["run_id"], "records": 27})
    PY

- [ ] **Step 5: Perform exact Slack API readback**

Run this self-contained readback:

    env/bin/python - <<'PY'
    import json
    import re
    from dotenv import load_dotenv

    load_dotenv('/Users/rob/env/tcsc-trips/.env', override=False)

    from app.slack.client import get_slack_client
    from scripts.validate_announcement import (
        MENTIONS,
        SCENARIOS,
        TEST_CHANNEL,
        _sanitize_for_test,
        _with_run_marker,
        build_scenario,
    )

    EMOJI = {
        '👨\u200d🏫': ':male-teacher:',
        '🌡️': ':thermometer:', '🌡': ':thermometer:',
        '☀️': ':sunny:', '☀': ':sunny:',
        '⚠️': ':warning:', '⚠': ':warning:',
        '🌫️': ':fog:', '🌫': ':fog:',
        '🍹': ':tropical_drink:', '🎿': ':ski:', '💨': ':dash:',
        '📅': ':date:', '📍': ':round_pushpin:', '📝': ':memo:',
        '🔦': ':flashlight:', '🚫': ':no_entry_sign:',
        '🧪': ':test_tube:',
    }
    BARE_URL = re.compile(
        r'(?<![<|])https://[^\s<>]+?(?=[.,;!?](?:\s|$)|\s|$)'
    )


    def canonical_string(value):
        for glyph, alias in EMOJI.items():
            value = value.replace(glyph, alias)
        return BARE_URL.sub(lambda match: f'<{match.group(0)}>', value)


    def normalize(value):
        if isinstance(value, str):
            return canonical_string(value)
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {
                key: normalize(item)
                for key, item in value.items()
                if key != 'block_id'
                and not (key == 'verbatim' and item is False)
                and not (key == 'emoji' and item is True)
            }
        return value


    def serialized(message):
        return json.dumps(
            {
                'text': message.get('text', ''),
                'blocks': message.get('blocks', []),
            },
            ensure_ascii=False,
        )


    state = json.load(open('validate_posted_ts.json'))
    records = state['records']
    run_id = state['run_id']
    client = get_slack_client()
    record_index = 0
    roots_read = replies_read = 0

    for name, scenario in SCENARIOS.items():
        expected_blocks, expected_fallback, expected_details = build_scenario(
            name, scenario
        )
        root_record = records[record_index]
        record_index += 1
        assert not root_record.get('thread_ts')
        messages = client.conversations_replies(
            channel=TEST_CHANNEL,
            ts=root_record['ts'],
            limit=100,
        )['messages']
        assert len(messages) == (2 if expected_details else 1), name
        root = next(
            item for item in messages if item['ts'] == root_record['ts']
        )
        marked_blocks = _sanitize_for_test(
            _with_run_marker(expected_blocks, run_id, name)
        )
        marked_fallback = _sanitize_for_test(
            f'[{run_id}] {expected_fallback}'
        )
        assert normalize(root['blocks']) == normalize(marked_blocks), name
        assert root['text'] == canonical_string(marked_fallback), name
        assert all(mention not in serialized(root) for mention in MENTIONS)
        assert {
            item['name'] for item in root.get('reactions', [])
        } == set(scenario.reaction_names), name

        if scenario.kind in {'standalone', 'combined'}:
            rsvp = [
                element['text']
                for block in root['blocks']
                if block.get('type') == 'context'
                for element in block.get('elements', [])
                if element.get('text', '').startswith('Bop ')
            ]
            assert len(rsvp) == 1, name
            has_supplemental = (
                'In addition to your attendance emoji' in rsvp[0]
            )
            assert rsvp[0].count('\n') == (1 if has_supplemental else 0)
            assert len(rsvp[0].splitlines()) == (
                2 if has_supplemental else 1
            )
        if scenario.kind == 'standalone':
            assert '*Where · ' in serialized(root), name
            assert '*Where:*' not in serialized(root), name

        if expected_details:
            detail_record = records[record_index]
            record_index += 1
            assert detail_record.get('thread_ts') == root_record['ts']
            detail = next(
                item for item in messages if item['ts'] == detail_record['ts']
            )
            detail_blocks, detail_fallback = expected_details
            marked_detail_blocks = _sanitize_for_test(
                _with_run_marker(
                    detail_blocks, run_id, name, details=True
                )
            )
            marked_detail_fallback = _sanitize_for_test(
                f'[{run_id}] {detail_fallback}'
            )
            assert normalize(detail['blocks']) == normalize(
                marked_detail_blocks
            ), name
            assert detail['text'] == canonical_string(
                marked_detail_fallback
            ), name
            assert all(
                mention not in serialized(detail) for mention in MENTIONS
            )
            replies_read += 1
        roots_read += 1

    assert record_index == len(records)
    assert (roots_read, replies_read) == (16, 11)
    print(json.dumps({
        'all_contracts': 'pass',
        'run_id': run_id,
        'roots_read': roots_read,
        'replies_read': replies_read,
        'reaction_errors': len(state.get('reaction_errors', [])),
    }, sort_keys=True))
    PY

Expected: `all_contracts` is `pass`, with 16 roots, 11 replies, and zero reaction errors.

If any assertion fails, keep validate_posted_ts.json and the posted messages for diagnosis; do not teardown until the mismatch is understood.

- [ ] **Step 6: Retain the final run for visual sign-off**

Append the reviewed commit, focused/full results, and run ID to .superpowers/sdd/progress.md. Do not teardown the successful run. Provide links for routine, supplemental standalone, cross-day combined, same-day combined without supplemental reactions, mixed cancellation, and weekly summary. Wait for product-owner sign-off before using superpowers:finishing-a-development-branch.
