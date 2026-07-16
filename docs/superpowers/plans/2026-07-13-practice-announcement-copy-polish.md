# Practice Announcement Copy Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved member-facing RSVP, supplemental-reaction, combined-session, Notes, and weekly-summary polish while preserving the correctness and lifecycle work already completed on the feature branch.

**Architecture:** Keep the existing builders and persistence model. Extend `app/practices/plan_reactions.py` with modifier-aware validation and small natural-language formatters, then let `app/slack/blocks/announcements.py` compose one bounded two-line RSVP context and tail-preserving accessibility fallback for standalone and combined roots. Keep weekly copy isolated in `app/slack/blocks/summary.py`; production orchestration continues to pass normalized reaction names through unchanged.

**Tech Stack:** Python 3.13, Flask, SQLAlchemy, Slack Block Kit and Slack SDK, pytest.

**Reference spec:** `docs/superpowers/specs/2026-07-13-practice-announcement-copy-polish-design.md`

**Builds on:** `docs/superpowers/plans/2026-07-12-practice-announcement-finalization.md`

## Global Constraints

- This is a copy-and-formatting addendum. Do not add a database migration, a new settings surface, an emoji picker, or a combined-session data model.
- Preserve saved reaction order, stored labels, the four-reaction maximum, the 80-character label limit, and defaults/override behavior already implemented.
- Accept only `base_emoji` or `base_emoji::skin-tone-N`, where `N` is 2 through 6; the normalized full reaction name is at most 80 characters.
- Check the base reaction against the reserved attendance set so a modifier cannot bypass the reservation.
- Slack rendering wraps a normalized name once; reaction seeding, reconciliation, and event matching use the full unwrapped name unchanged.
- The RSVP ending is exactly one `context` block with one `mrkdwn` element and exactly one intentional newline. Coach/lead attribution remains a separate context block.
- Standalone attendance copy is exact: `Bop :white_check_mark: so we'll know you'll be there.`
- The second RSVP line is exact: `Running late? Reply in the thread. <!channel>`
- Supplemental copy begins `In addition to your attendance emoji, hit` and uses natural one/two/Oxford-comma grammar with exactly one final period.
- Display-only label normalization removes terminal whitespace and `.`, `?`, or `!`; it does not mutate saved labels. A punctuation-only display label is invalid.
- Accessibility fallbacks use plain reaction names, contain no raw Slack shortcodes or `<!channel>`, and retain the complete RSVP/supplemental/late-arrival tail within 4,000 characters.
- Only supplemental copy may be shortened inside the 2,000-character context budget; attendance and the complete second line are reserved first.
- Combined same-day classification considers every displayed sibling, including cancelled sessions; attendance mappings include active sessions only.
- Combined supplemental copy appears only when every displayed sibling has the same ordered saved reaction list. All-cancelled roots omit RSVP, supplemental, and late-arrival copy.
- Member-facing Notes headings are exact `*📝 Notes*`; fallback headings stay plain `Notes:`.
- Weekly Block Kit uses one `📅` in the header, no calendar emoji on day rows, `🚫` only for cancellations, and the exact active-week footer `📝 Full practice details will be posted before each practice. · <!channel>`.
- Weekly fallback remains emoji-independent and contains no raw broadcast token.
- Do not alter Details-thread content, urgent-exception promotion, scheduling, database lifecycle compensation, or the recursive live-harness broadcast sanitizer.
- Use `env/bin/pytest` with explicit test paths. The full suite requires the repository's local PostgreSQL test service; do not point tests at any non-local database.
- Live validation is synthetic, posts only to `C07G9RTMRT3`, records every timestamp immediately, and requires successful teardown of the current state before reposting.

---

## File Structure

### Modify

- `app/practices/plan_reactions.py`: normalized skin-tone syntax, display-label normalization, visible supplemental sentence, and plain fallback sentence.
- `app/slack/blocks/announcements.py`: shared bounded RSVP context, tail-preserving fallbacks, Notes icon, and combined-session hierarchy/mappings.
- `app/slack/practices/announcements.py`: keep full modifier names intact and ensure any initial combined seed list exposes active attendance reactions only.
- `app/slack/blocks/summary.py`: weekly header, cancellation cue, and fixed active-week footer.
- `scripts/validate_announcement.py`: approved Rollerski/Run reaction fixture, same-day combined fixture, and active-only synthetic reaction seeds.
- `tests/practices/test_plan_reactions.py`: validation, sentence grammar, punctuation, escaping, and fallback naming.
- `tests/routes/test_admin_practice_plan_reactions.py`: wrapped modifier normalization and reserved-base rejection through Settings.
- `tests/slack/test_practice_create_modal.py`: Slack creation-modal modifier parsing and formatting.
- `tests/slack/test_practice_edit_full.py`: admin/Slack edit snapshot round trip.
- `tests/slack/test_details_reply_wiring.py`: initial seed and refresh reconciliation with the full modifier name.
- `tests/slack/test_reaction_rsvp.py`: modifier reactions remain non-attendance.
- `tests/slack/test_announcement_blocks.py`: exact standalone context, Notes, fallback, and length contracts.
- `tests/slack/test_combined_announcements.py`: same-day/cross-day hierarchy, active mappings, cancellation, fallback, and seeding contracts.
- `tests/slack/test_weekly_summary_blocks.py`: exact Unicode Block Kit copy and unchanged plain fallback.
- `tests/scripts/test_validate_announcement.py`: scenario registry, exact approved payloads, full reaction-name pass-through, and existing safety invariants.

### Verify Without Planned Changes

- `tests/agent/test_weekly_summary.py`: scheduled weekly integration still uses the final builder output.
- `tests/slack/test_refresh.py`: refresh keeps using the public builders and prior snapshots.
- `tests/slack/test_refresh_delete_exclusion.py`: cancellation/deletion and weekly refresh safety remain intact.
- `tests/test_scheduler_practice_announcements.py`: existing compatible Strength grouping remains intact.

### Do Not Modify

- Database models or migrations.
- Settings/default ownership or per-practice snapshot semantics.
- `app/slack/blocks/text.py`; import its existing `CONTEXT_TEXT_MAX` and `FALLBACK_TEXT_MAX` constants instead.
- Harness channel guards, mention sanitizer, state persistence, CLI destination, or teardown algorithm.

---

### Task 1: Add modifier-aware Plan-reaction grammar

**Files:**

- Modify: `app/practices/plan_reactions.py`
- Modify: `tests/practices/test_plan_reactions.py`
- Modify: `tests/routes/test_admin_practice_plan_reactions.py`
- Modify: `tests/slack/test_practice_create_modal.py`
- Modify: `tests/slack/test_practice_edit_full.py`
- Modify: `tests/slack/test_details_reply_wiring.py`
- Modify: `tests/slack/test_reaction_rsvp.py`

**Interfaces:**

- Produces: `MAX_PLAN_REACTION_NAME = 80`.
- Produces: `format_reaction_name_for_fallback(name: str) -> str`.
- Produces: `format_supplemental_reaction_sentence(reactions: Iterable[Mapping[str, str]]) -> str`.
- Produces: `format_supplemental_reaction_fallback(reactions: Iterable[Mapping[str, str]]) -> str`.
- Preserves: `normalize_plan_reactions()`, `resolve_default_plan_reactions()`, `parse_plan_reaction_lines()`, `format_plan_reaction_lines()`, `format_plan_reaction_legend()`, and `plan_reaction_names()`.
- Consumed by: Task 2 and Task 3 announcement builders.

- [ ] **Step 1: Write failing domain tests for syntax, natural grammar, and display-only normalization**

Add these imports and tests to `tests/practices/test_plan_reactions.py`:

```python
from copy import deepcopy

from app.practices.plan_reactions import (
    MAX_PLAN_REACTION_NAME,
    format_reaction_name_for_fallback,
    format_supplemental_reaction_fallback,
    format_supplemental_reaction_sentence,
    plan_reaction_names,
)


def test_skin_tone_bare_and_wrapped_names_normalize_and_round_trip():
    expected = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    assert parse_plan_reaction_lines(
        "older_adult::skin-tone-4 experienced rollerskier"
    ) == expected
    assert parse_plan_reaction_lines(
        ":older_adult::skin-tone-4: experienced rollerskier"
    ) == expected
    assert format_plan_reaction_lines(expected) == (
        ":older_adult::skin-tone-4: experienced rollerskier"
    )
    assert plan_reaction_names(expected) == ["older_adult::skin-tone-4"]


def test_different_skin_tones_on_one_base_remain_distinct_names():
    reactions = normalize_plan_reactions([
        {"emoji": "older_adult::skin-tone-3", "label": "Group three"},
        {"emoji": "older_adult::skin-tone-4", "label": "Group four"},
    ])
    assert plan_reaction_names(reactions) == [
        "older_adult::skin-tone-3",
        "older_adult::skin-tone-4",
    ]


@pytest.mark.parametrize(
    "emoji",
    [
        "older_adult::skin-tone-1",
        "older_adult::skin-tone-7",
        "older_adult::skin-tone-4::skin-tone-5",
        "older_adult:skin-tone-4",
        "::skin-tone-4",
        "older_adult::skin_tone_4",
    ],
)
def test_malformed_skin_tone_names_are_rejected(emoji):
    with pytest.raises(PlanReactionValidationError, match="Slack emoji shortcode"):
        normalize_plan_reactions([{"emoji": emoji, "label": "Choice"}])


def test_modifier_cannot_bypass_reserved_attendance_base():
    with pytest.raises(PlanReactionValidationError, match="reserved"):
        normalize_plan_reactions([{
            "emoji": "white_check_mark::skin-tone-4",
            "label": "Not allowed",
        }])


def test_normalized_reaction_name_length_boundary():
    suffix = "::skin-tone-4"
    allowed = "x" * (MAX_PLAN_REACTION_NAME - len(suffix)) + suffix
    assert normalize_plan_reactions([{
        "emoji": allowed,
        "label": "Allowed",
    }])[0]["emoji"] == allowed
    with pytest.raises(PlanReactionValidationError, match="80 characters"):
        normalize_plan_reactions([{
            "emoji": "x" * (MAX_PLAN_REACTION_NAME - len(suffix) + 1) + suffix,
            "label": "Too long",
        }])


@pytest.mark.parametrize(
    ("reactions", "expected"),
    [
        ([], ""),
        (
            [{"emoji": "hatching_chick", "label": "new rollerskier"}],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {
                    "emoji": "older_adult::skin-tone-4",
                    "label": "experienced rollerskier",
                },
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult::skin-tone-4: for experienced "
            "rollerskier, and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "older_adult", "label": "experienced rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
                {"emoji": "evergreen_tree", "label": "endurance"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult: for experienced rollerskier, "
            "a :athletic_shoe: for runner, and a :evergreen_tree: for endurance.",
        ),
    ],
)
def test_supplemental_instruction_has_exact_zero_to_four_choice_grammar(
    reactions, expected
):
    assert format_supplemental_reaction_sentence(reactions) == expected


def test_supplemental_fallback_uses_plain_names_and_semicolon_grammar():
    reactions = [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ]
    assert format_reaction_name_for_fallback(
        "older_adult::skin-tone-4"
    ) == "older adult, skin tone 4"
    assert format_reaction_name_for_fallback("six") == "six"
    assert format_supplemental_reaction_fallback(reactions) == (
        "Additional reactions: hatching chick for new rollerskier; "
        "older adult, skin tone 4 for experienced rollerskier; "
        "athletic shoe for runner."
    )
    assert format_supplemental_reaction_fallback(reactions[:1]) == (
        "Additional reaction: hatching chick for new rollerskier."
    )


def test_display_labels_normalize_punctuation_without_mutating_saved_values():
    reactions = [
        {"emoji": "hatching_chick", "label": "New <skier>?!  "},
        {"emoji": "athletic_shoe", "label": "Runner."},
    ]
    original = deepcopy(reactions)
    assert format_supplemental_reaction_sentence(reactions) == (
        "In addition to your attendance emoji, hit a :hatching_chick: "
        "for New &lt;skier&gt; and a :athletic_shoe: for Runner."
    )
    assert format_supplemental_reaction_fallback(reactions) == (
        "Additional reactions: hatching chick for New <skier>; "
        "athletic shoe for Runner."
    )
    assert reactions == original


@pytest.mark.parametrize("label", [".", "?!", "...   "])
def test_punctuation_only_label_is_rejected(label):
    with pytest.raises(PlanReactionValidationError, match="label is required"):
        normalize_plan_reactions([{"emoji": "snowflake", "label": label}])
```

- [ ] **Step 2: Add failing ingress and pass-through regressions**

Add these focused cases beside the existing equivalent tests:

```python
# tests/routes/test_admin_practice_plan_reactions.py
def test_settings_normalizes_wrapped_skin_tone_name(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/activities/create",
        json={
            "name": "Plan Reaction Modifier Rollerski",
            "gear_required": [],
            "default_plan_reactions": [{
                "emoji": ":older_adult::skin-tone-4:",
                "label": "experienced rollerskier",
            }],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]


def test_settings_rejects_reserved_base_with_modifier(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/types/create",
        json={
            "name": "Plan Reaction Modifier Invalid",
            "default_plan_reactions": [{
                "emoji": "white_check_mark::skin-tone-4",
                "label": "Wrong",
            }],
        },
    )
    assert response.status_code == 400
    assert response.get_json()["field"] == "default_plan_reactions"


# tests/slack/test_practice_create_modal.py
def test_create_submission_preserves_full_skin_tone_reaction_name():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            plan_text=":older_adult::skin-tone-4: experienced rollerskier"
        ),
        include_plan_reactions=True,
    )
    assert errors == {}
    assert fields["plan_reactions"] == [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]


# tests/slack/test_practice_edit_full.py
def test_full_edit_modal_wraps_skin_tone_name_once():
    practice = _practice_info()
    practice.plan_reactions = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    field = _blocks_by_id(
        build_practice_edit_full_modal(practice)
    )["plan_reactions_block"]
    assert field["element"]["initial_value"] == (
        ":older_adult::skin-tone-4: experienced rollerskier"
    )
```

In `tests/slack/test_details_reply_wiring.py`, change the existing initial-seed fixture from `snowflake` to `older_adult::skin-tone-4` and assert:

```python
assert mock_client.reactions_add.call_args_list == [
    call(channel="CTEST", timestamp="1111.0001", name="white_check_mark"),
    call(
        channel="CTEST",
        timestamp="1111.0001",
        name="older_adult::skin-tone-4",
    ),
]
```

In `test_plan_reaction_change_reconciles_only_the_diff` in the same file,
replace the current `practice.plan_reactions`, `previous`, and final
`reactions_add` expectation with:

```python
practice.plan_reactions = [{
    "emoji": "older_adult::skin-tone-4",
    "label": "experienced rollerskier",
}]
previous = [{"emoji": "old_choice", "label": "Old choice"}]

client.reactions_add.assert_called_once_with(
    channel="CTEST",
    timestamp="1234.5678",
    name="older_adult::skin-tone-4",
)
```

Add `"older_adult::skin-tone-4"` to the parameter list of `test_non_attendance_reactions_are_ignored` in `tests/slack/test_reaction_rsvp.py`.

- [ ] **Step 3: Run the focused tests and confirm the new contracts fail for the intended reason**

Run:

```bash
env/bin/pytest -q \
  tests/practices/test_plan_reactions.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_reaction_rsvp.py
```

Expected: failures show that the current parser rejects `::skin-tone-4`, the new formatter imports do not exist, and the initial post omits the modified reaction after normalization fails. Existing unrelated tests remain green.

- [ ] **Step 4: Implement strict modifier normalization and sentence formatters**

Replace the regex constants and `_normalize_emoji()` in `app/practices/plan_reactions.py` with:

```python
MAX_PLAN_REACTIONS = 4
MAX_PLAN_REACTION_LABEL = 80
MAX_PLAN_REACTION_NAME = 80

_BASE_EMOJI_PATTERN = r"[a-z0-9_+\-]+"
_SKIN_TONE_PATTERN = r"skin-tone-[2-6]"
_NORMALIZED_EMOJI_PATTERN = (
    rf"{_BASE_EMOJI_PATTERN}(?:::{_SKIN_TONE_PATTERN})?"
)
EMOJI_RE = re.compile(
    rf"^(?P<base>{_BASE_EMOJI_PATTERN})"
    rf"(?:::(?P<modifier>{_SKIN_TONE_PATTERN}))?$"
)
LINE_RE = re.compile(
    rf"^\s*(?P<emoji>"
    rf":(?:{_NORMALIZED_EMOJI_PATTERN}):|"
    rf"(?:{_NORMALIZED_EMOJI_PATTERN})"
    rf")\s+(?P<label>.+?)\s*$"
)


def _normalize_emoji(value: object, source: str) -> str:
    emoji = str(value or "").strip().lower()
    if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
        emoji = emoji[1:-1]
    if len(emoji) > MAX_PLAN_REACTION_NAME:
        raise PlanReactionValidationError(
            f"{source}: emoji name must be {MAX_PLAN_REACTION_NAME} characters or fewer"
        )
    match = EMOJI_RE.fullmatch(emoji)
    if not match:
        raise PlanReactionValidationError(
            f"{source}: enter a Slack emoji shortcode"
        )
    if match.group("base") in RESERVED_ATTENDANCE_EMOJIS:
        raise PlanReactionValidationError(
            f"{source}: :{emoji}: is reserved for attendance"
        )
    return emoji
```

Change the parser row to use the single captured token:

```python
rows.append({
    "emoji": match.group("emoji"),
    "label": match.group("label"),
})
```

Add these helpers below `format_plan_reaction_legend()`:

```python
def _display_label(label: str, source: str) -> str:
    display = re.sub(r"[.?!]+$", "", str(label).rstrip()).rstrip()
    if not display:
        raise PlanReactionValidationError(f"{source}: label is required")
    return display


def _escape_slack_label(label: str) -> str:
    return label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _natural_join(items: list[str], *, conjunction: str) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"


def format_reaction_name_for_fallback(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if normalized.startswith(":") and normalized.endswith(":") and len(normalized) > 2:
        normalized = normalized[1:-1]
    if len(normalized) > MAX_PLAN_REACTION_NAME or not EMOJI_RE.fullmatch(normalized):
        raise PlanReactionValidationError(
            "Reaction name: enter a Slack emoji shortcode"
        )
    base, separator, modifier = normalized.partition("::")
    rendered = base.replace("_", " ")
    if separator:
        rendered += ", " + modifier.replace("-", " ")
    return rendered


def format_supplemental_reaction_sentence(
    reactions: Iterable[Mapping[str, str]],
) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    if not normalized:
        return ""
    clauses = [
        f"a :{item['emoji']}: for "
        f"{_escape_slack_label(_display_label(item['label'], 'Plan reactions'))}"
        for item in normalized
    ]
    return (
        "In addition to your attendance emoji, hit "
        + _natural_join(clauses, conjunction="and")
        + "."
    )


def format_supplemental_reaction_fallback(
    reactions: Iterable[Mapping[str, str]],
) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    if not normalized:
        return ""
    clauses = [
        f"{format_reaction_name_for_fallback(item['emoji'])} for "
        f"{_display_label(item['label'], 'Plan reactions')}"
        for item in normalized
    ]
    heading = "Additional reaction" if len(clauses) == 1 else "Additional reactions"
    return f"{heading}: {'; '.join(clauses)}."
```

After the existing nonblank and single-line label checks in `normalize_plan_reactions()`, validate display content without assigning it back:

```python
_display_label(label, item_source)
```

Keep `format_plan_reaction_legend()` for compatibility, but announcement builders must stop importing it in Tasks 2 and 3.

- [ ] **Step 5: Run domain, ingress, seed, and event tests**

Run the Step 3 command again.

Expected: all selected tests pass. Confirm the seed assertion contains the exact unwrapped string `older_adult::skin-tone-4` and no test expects an emoji catalog lookup.

- [ ] **Step 6: Commit the domain and pass-through contract**

```bash
git add \
  app/practices/plan_reactions.py \
  tests/practices/test_plan_reactions.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_reaction_rsvp.py
git commit -m "feat(practices): polish supplemental reaction grammar"
```

---

### Task 2: Restore the standalone RSVP ending and bounded fallback

**Files:**

- Modify: `app/slack/blocks/announcements.py`
- Modify: `tests/slack/test_announcement_blocks.py`

**Interfaces:**

- Consumes: `format_supplemental_reaction_sentence()` and `format_supplemental_reaction_fallback()` from Task 1.
- Produces: `_rsvp_context_block(attendance_sentence: str, reactions, *, surface: str, practice_id=None) -> dict`.
- Produces: `_fallback_with_reserved_tail(parts: list[str], tail: str, *, surface: str, practice_id=None) -> str`.
- Produces constants reused by Task 3: `_RUNNING_LATE_LINE`, `_FALLBACK_RUNNING_LATE`.

- [ ] **Step 1: Replace old standalone expectations with exact failing context contracts**

Replace `test_saved_plan_reactions_use_exact_rsvp_and_plan_grammar`,
`test_plan_heading_is_absent_without_saved_reactions`,
`test_rsvp_omits_root_channel_and_running_late_copy`, and
`test_coach_and_lead_context_remains_after_contiguous_plan_legend` with the
helper and exact tests below. Update
`test_long_workout_and_alerts_cannot_remove_required_fallback_end` to use the
new plain tail assertions shown below rather than retaining its old
`RSVP with ✅.` or `Your Practice Plan:` expectations.

```python
def _rsvp_context(blocks):
    matches = [
        block for block in blocks
        if block.get("type") == "context"
        and block.get("elements")
        and block["elements"][0].get("text", "").startswith("Bop ")
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    ("reactions", "supplemental"),
    [
        ([], ""),
        (
            [{"emoji": "hatching_chick", "label": "new rollerskier"}],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {
                    "emoji": "older_adult::skin-tone-4",
                    "label": "experienced rollerskier",
                },
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult::skin-tone-4: for experienced "
            "rollerskier, and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "older_adult", "label": "experienced rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
                {"emoji": "evergreen_tree", "label": "endurance"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult: for experienced rollerskier, "
            "a :athletic_shoe: for runner, and a :evergreen_tree: for endurance.",
        ),
    ],
)
def test_standalone_rsvp_is_one_two_line_context(
    practice_info, conditions, reactions, supplemental
):
    practice_info.plan_reactions = reactions
    block = _rsvp_context(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert block["elements"] == [{
        "type": "mrkdwn",
        "text": (
            "Bop :white_check_mark: so we'll know you'll be there."
            f"{supplemental}\n"
            "Running late? Reply in the thread. <!channel>"
        ),
    }]
    assert block["elements"][0]["text"].count("\n") == 1


def test_context_budget_preserves_attendance_and_complete_second_line(monkeypatch):
    monkeypatch.setattr(
        announcement_blocks,
        "format_supplemental_reaction_sentence",
        lambda reactions: "s" * 3_000,
    )
    block = announcement_blocks._rsvp_context_block(
        "Bop :white_check_mark: so we'll know you'll be there.",
        [],
        surface="practice_announcement",
        practice_id=42,
    )
    text = block["elements"][0]["text"]
    assert len(text) <= 2_000
    assert text.startswith(
        "Bop :white_check_mark: so we'll know you'll be there. "
    )
    assert text.endswith("\nRunning late? Reply in the thread. <!channel>")
    assert text.count("\n") == 1


def test_coach_context_stays_separate_from_rsvp_context(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    rsvp = _rsvp_context(blocks)
    coach = next(
        block for block in blocks
        if block.get("type") == "context"
        and "Coach <@U1>" in str(block.get("elements"))
    )
    assert rsvp is not coach
    assert "Coach" not in rsvp["elements"][0]["text"]


def test_member_facing_notes_heading_uses_memo_icon(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    notes = next(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
        and "Meet at the flagpole" in block.get("text", {}).get("text", "")
    )
    assert notes.startswith("*📝 Notes*\n")
    assert "📌" not in notes
```

Replace the old fallback-tail assertion with:

```python
def test_standalone_fallback_has_exact_plain_rsvp_tail(
    practice_info, conditions
):
    practice_info.plan_reactions = [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ]
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reactions: hatching chick for new rollerskier; "
        "older adult, skin tone 4 for experienced rollerskier; "
        "athletic shoe for runner. Running late? Reply in the thread."
    )
    assert "<!channel>" not in fallback
    assert ":hatching_chick:" not in fallback


def test_standalone_fallback_without_supplement_has_exact_plain_tail(
    practice_info, conditions
):
    practice_info.plan_reactions = []
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )


def test_long_standalone_content_preserves_complete_required_tail(
    practice_info, conditions
):
    practice_info.workout_description = "w" * 10_000
    practice_info.logistics_notes = "n" * 10_000
    practice_info.plan_reactions = [
        {"emoji": "evergreen_tree", "label": "Endurance instead"}
    ]
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead. "
        "Running late? Reply in the thread."
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX


def test_reserved_fallback_helper_never_truncates_required_tail():
    tail = (
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )
    fallback = announcement_blocks._fallback_with_reserved_tail(
        ["body " * 2_000],
        tail,
        surface="practice_announcement",
        practice_id=42,
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX
    assert fallback.endswith(tail)
```

- [ ] **Step 2: Run the standalone block tests and verify the old grammar fails**

Run:

```bash
env/bin/pytest -q tests/slack/test_announcement_blocks.py
```

Expected: failures show `Bop ✅ if you're coming.`, the removed `Your Practice Plan:` heading, missing late/channel copy, the pin icon, and the old fallback tail.

- [ ] **Step 3: Add bounded shared context and fallback helpers**

Replace the Plan-reaction import and extend the Slack-text imports in `app/slack/blocks/announcements.py`:

```python
from app.practices.plan_reactions import (
    format_supplemental_reaction_fallback,
    format_supplemental_reaction_sentence,
)
from app.slack.blocks.text import (
    CONTEXT_TEXT_MAX,
    FALLBACK_TEXT_MAX,
    HEADER_TEXT_MAX,
    SECTION_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)
```

Remove `_FALLBACK_PLAN_MAX` and `_COMBINED_FALLBACK_PLAN_MAX`, then add:

```python
_RUNNING_LATE_LINE = "Running late? Reply in the thread. <!channel>"
_FALLBACK_RUNNING_LATE = "Running late? Reply in the thread."
_STANDALONE_ATTENDANCE = (
    "Bop :white_check_mark: so we'll know you'll be there."
)
_STANDALONE_FALLBACK_ATTENDANCE = (
    "RSVP with the white check mark reaction so we'll know you'll be there."
)


def _rsvp_context_block(
    attendance_sentence,
    reactions,
    *,
    surface,
    practice_id=None,
):
    supplemental = format_supplemental_reaction_sentence(reactions)
    required = f"{attendance_sentence}\n{_RUNNING_LATE_LINE}"
    if supplemental:
        budget = CONTEXT_TEXT_MAX - len(required) - 1
        supplemental = truncate_slack_text(
            supplemental,
            max(1, budget),
            field="plan_reactions",
            surface=surface,
            practice_id=practice_id,
        )
    first_line = attendance_sentence
    if supplemental:
        first_line += " " + supplemental
    return {
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"{first_line}\n{_RUNNING_LATE_LINE}",
        }],
    }


def _fallback_with_reserved_tail(
    parts,
    tail,
    *,
    surface,
    practice_id=None,
):
    body = " ".join(
        str(part).strip() for part in parts
        if part and str(part).strip()
    )
    tail = str(tail).strip()
    separator_length = 1 if body and tail else 0
    body_budget = max(0, FALLBACK_TEXT_MAX - len(tail) - separator_length)
    if body and len(body) > body_budget:
        body = (
            truncate_slack_text(
                body,
                body_budget,
                field="fallback_body",
                surface=surface,
                practice_id=practice_id,
            )
            if body_budget > 0
            else ""
        )
    value = " ".join(part for part in (body, tail) if part)
    return guard_fallback_text(
        value,
        surface=surface,
        practice_id=practice_id,
    )
```

- [ ] **Step 4: Wire standalone blocks and fallbacks to the shared helpers**

Change the Notes prefix to:

```python
notes_prefix = "*📝 Notes*\n"
```

Replace the standalone `rsvp_lines`/`Your Practice Plan` construction with:

```python
ending_group = [
    _rsvp_context_block(
        _STANDALONE_ATTENDANCE,
        getattr(practice, "plan_reactions", None) or [],
        surface="practice_announcement",
        practice_id=practice.id,
    )
]
```

Keep the existing coach/lead block appended to `ending_group` unchanged.

At the end of `build_practice_fallback_text()`, replace `RSVP with ✅.`, the Plan legend, and the final generic join with:

```python
tail_parts = [_STANDALONE_FALLBACK_ATTENDANCE]
supplemental = format_supplemental_reaction_fallback(
    getattr(practice, "plan_reactions", None) or []
)
if supplemental:
    tail_parts.append(supplemental)
tail_parts.append(_FALLBACK_RUNNING_LATE)
return _fallback_with_reserved_tail(
    parts,
    " ".join(tail_parts),
    surface="practice_announcement",
    practice_id=practice.id,
)
```

- [ ] **Step 5: Run standalone tests and inspect the exact structure**

Run:

```bash
env/bin/pytest -q tests/slack/test_announcement_blocks.py
```

Expected: all tests pass; the RSVP context has one element and one newline, the lead context is separate, fallback ends with the complete plain tail, and the Notes section starts with `*📝 Notes*`.

- [ ] **Step 6: Commit standalone copy and boundary handling**

```bash
git add app/slack/blocks/announcements.py tests/slack/test_announcement_blocks.py
git commit -m "feat(slack): restore standalone RSVP guidance"
```

---

### Task 3: Simplify combined-session hierarchy and active RSVP mapping

**Files:**

- Modify: `app/slack/blocks/announcements.py`
- Modify: `app/slack/practices/announcements.py`
- Modify: `tests/slack/test_combined_announcements.py`

**Interfaces:**

- Consumes: `_rsvp_context_block()`, `_fallback_with_reserved_tail()`, `_FALLBACK_RUNNING_LATE`, and Task 1's fallback reaction-name formatter.
- Produces: `_all_sessions_same_date(practices) -> bool`.
- Produces: `_combined_session_when(practice, *, same_day: bool) -> str`.
- Produces: `_combined_owner_label(practice, *, same_day: bool) -> str`.
- Produces: `_combined_mapping(practices, *, plain: bool) -> str | None`.
- Produces: `_combined_attendance_sentence(practices, *, plain: bool) -> str | None`.

- [ ] **Step 1: Write failing same-day, cross-day, cancellation, and hierarchy tests**

Extend `combined_practice()` in `tests/slack/test_combined_announcements.py` with a `minute=15` keyword and use it in the fixture date:

```python
def combined_practice(
    practice_id,
    day,
    hour,
    emoji,
    *,
    minute=15,
    status=PracticeStatus.SCHEDULED,
    reason=None,
    workout="3 x 8 strength circuit",
    notes="Bring indoor shoes",
    social=None,
    plan=None,
):
    return SimpleNamespace(
        id=practice_id,
        date=datetime(2026, 7, day, hour, minute),
        status=status,
        slack_session_emoji=emoji,
        location=SimpleNamespace(id=10, name="Balance Fitness", spot=None),
        activities=[SimpleNamespace(id=1, name="Strength")],
        practice_types=[SimpleNamespace(id=2, name="Strength")],
        workout_description=workout,
        logistics_notes=notes,
        has_social=social is not None,
        social_location=(
            SimpleNamespace(id=20, name=social) if social is not None else None
        ),
        plan_reactions=list(plan or []),
        leads=[],
        cancellation_reason=reason,
    )
```

Replace the old copy-specific tests
`test_combined_uses_saved_session_map_and_shared_plan_grammar`,
`test_cancelled_slot_and_fallback_keep_every_session_distinct`,
`test_one_survivor_keeps_combined_grammar_and_saved_reaction`,
`test_post_creation_divergence_keeps_each_sessions_content_visible`,
`test_combined_fallback_normal_shared_copy_is_exact`, and
`_assert_combined_fallback_tail_is_accessible` with the exact contracts below.
Update `test_different_plan_snapshots_hide_shared_plan_legend` to assert that
`In addition to your attendance emoji` and both supplemental shortcodes are
absent. Retain its differing-snapshot fixture.

```python
def _combined_rsvp_text(blocks):
    matches = [
        item["text"]
        for block in blocks
        if block.get("type") == "context"
        for item in block.get("elements", [])
        if item.get("text", "").startswith("Bop ")
    ]
    assert len(matches) == 1
    return matches[0]


def test_cross_day_mapping_is_only_in_bottom_context():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(2, 15, 19, "seven"),
    ]
    blocks = build_combined_lift_blocks(practices)
    text = rendered_text(blocks)
    assert "Choose a session:" not in text
    assert ":six: *Tuesday" not in text
    assert ":seven: *Wednesday" not in text
    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM "
        "so we'll know you'll be there.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_combined_shared_plan_is_appended_to_attendance_line():
    plan = [{
        "emoji": "hatching_chick",
        "label": "first strength practice support",
    }]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]
    assert _combined_rsvp_text(build_combined_lift_blocks(practices)) == (
        "Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM "
        "so we'll know you'll be there. In addition to your attendance emoji, "
        "hit a :hatching_chick: for first strength practice support.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_same_day_rows_and_mapping_use_times_only():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(2, 14, 19, "seven", minute=20),
    ]
    blocks = build_combined_lift_blocks(practices)
    text = rendered_text(blocks)
    assert "*6:05 PM*" in text
    assert "*7:20 PM*" in text
    assert "Tuesday, July 14 · 6:05 PM" not in text
    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for 6:05 PM or :seven: for 7:20 PM "
        "so we'll know you'll be there.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_same_day_cancelled_sibling_keeps_time_only_active_mapping():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(
            2,
            14,
            19,
            "seven",
            minute=20,
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    rsvp = _combined_rsvp_text(build_combined_lift_blocks(practices))
    assert rsvp.startswith(
        "Bop :six: for 6:05 PM so we'll know you'll be there."
    )
    assert "Tue at" not in rsvp
    assert ":seven: for" not in rsvp


def test_three_active_sessions_use_oxford_or_mapping():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(2, 15, 19, "seven"),
        combined_practice(3, 16, 20, "eight"),
    ]
    assert _combined_rsvp_text(build_combined_lift_blocks(practices)).startswith(
        "Bop :six: for Tue at 6:15 PM, :seven: for Wed at 7:15 PM, "
        "or :eight: for Thu at 8:15 PM so we'll know you'll be there."
    )


def test_cancelled_sibling_stays_visible_but_leaves_cross_day_mapping():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    blocks = build_combined_lift_blocks(practices)
    assert "Facility closed" in rendered_text(blocks)
    assert _combined_rsvp_text(blocks).startswith(
        "Bop :six: for Tue at 6:15 PM so we'll know you'll be there."
    )
    assert ":seven: for" not in _combined_rsvp_text(blocks)


def test_one_displayed_session_keeps_combined_reaction_grammar():
    blocks = build_combined_lift_blocks([
        combined_practice(2, 15, 19, "seven")
    ])
    rsvp = _combined_rsvp_text(blocks)
    assert rsvp.startswith(
        "Bop :seven: for 7:15 PM so we'll know you'll be there."
    )
    assert ":white_check_mark:" not in rsvp


def test_all_cancelled_combined_root_has_no_rsvp_context_or_fallback_tail():
    plan = [{"emoji": "hatching_chick", "label": "new rollerskier"}]
    practices = [
        combined_practice(
            1,
            14,
            18,
            "six",
            status=PracticeStatus.CANCELLED,
            reason="Closed",
            plan=plan,
        ),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Closed",
            plan=plan,
        ),
    ]
    blocks = build_combined_lift_blocks(practices)
    fallback = build_combined_fallback_text(practices)
    assert not any(
        item.get("text", "").startswith("Bop ")
        for block in blocks if block.get("type") == "context"
        for item in block.get("elements", [])
    )
    for forbidden in ("RSVP", "Additional reaction", "Running late"):
        assert forbidden not in fallback


def test_cancelled_sibling_with_different_plan_suppresses_supplemental_copy():
    active = combined_practice(
        1,
        14,
        18,
        "six",
        plan=[{"emoji": "hatching_chick", "label": "new rollerskier"}],
    )
    cancelled = combined_practice(
        2,
        15,
        19,
        "seven",
        status=PracticeStatus.CANCELLED,
        reason="Closed",
        plan=[{"emoji": "athletic_shoe", "label": "runner"}],
    )
    assert "In addition" not in _combined_rsvp_text(
        build_combined_lift_blocks([active, cancelled])
    )


def test_different_notes_keep_exact_heading_and_text_owner():
    practices = [
        combined_practice(1, 14, 18, "six", notes="Shoes A"),
        combined_practice(2, 15, 19, "seven", notes="Shoes B"),
    ]
    notes_sections = [
        block["text"]["text"] for block in build_combined_lift_blocks(practices)
        if block.get("type") == "section"
        and block.get("text", {}).get("text", "").startswith("*📝 Notes*")
    ]
    assert notes_sections == [
        "*📝 Notes*\n*Tuesday at 6:15 PM*\nShoes A",
        "*📝 Notes*\n*Wednesday at 7:15 PM*\nShoes B",
    ]
    assert all(":six:" not in text and ":seven:" not in text for text in notes_sections)


def test_divergent_workout_and_social_use_text_owners_not_reactions():
    practices = [
        combined_practice(
            1,
            14,
            18,
            "six",
            workout="Session A circuit",
            social="Cafe A",
        ),
        combined_practice(
            2,
            15,
            19,
            "seven",
            workout="Session B circuit",
            social="Cafe B",
        ),
    ]
    sections = [
        block["text"]["text"] for block in build_combined_lift_blocks(practices)
        if block.get("type") == "section"
    ]
    owned = "\n".join(
        text for text in sections
        if "Session A" in text or "Session B" in text or "Cafe A" in text or "Cafe B" in text
    )
    assert "Tuesday at 6:15 PM" in owned
    assert "Wednesday at 7:15 PM" in owned
    assert ":six:" not in owned
    assert ":seven:" not in owned
```

Replace the old exact combined fallback with:

```python
def test_combined_fallback_uses_plain_active_mapping_and_complete_tail():
    plan = [{"emoji": "hatching_chick", "label": "first strength support"}]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM or seven for Wed at 7:15 PM "
        "so we'll know you'll be there. Additional reaction: hatching chick "
        "for first strength support. Running late? Reply in the thread."
    )
    assert "session :six:" not in fallback
    assert "<!channel>" not in fallback


def test_same_day_combined_fallback_uses_time_only_mapping():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(2, 14, 19, "seven", minute=20),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for 6:05 PM or seven for 7:20 PM "
        "so we'll know you'll be there. Running late? Reply in the thread."
    )
    assert "six for Tue" not in fallback


def test_mixed_cancelled_fallback_maps_only_active_session():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    fallback = build_combined_fallback_text(practices)
    assert "CANCELLED: Facility closed" in fallback
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )
    assert "seven for" not in fallback


def test_long_combined_content_preserves_complete_required_tail():
    plan = [{"emoji": "evergreen_tree", "label": "endurance"}]
    practices = [
        combined_practice(1, 14, 18, "six", workout="w" * 10_000, plan=plan),
        combined_practice(2, 15, 19, "seven", notes="n" * 10_000, plan=plan),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM or seven for Wed at 7:15 PM "
        "so we'll know you'll be there. Additional reaction: evergreen tree "
        "for endurance. Running late? Reply in the thread."
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX
```

- [ ] **Step 2: Run combined tests and verify the existing duplicated hierarchy fails**

Run:

```bash
env/bin/pytest -q tests/slack/test_combined_announcements.py
```

Expected: failures show `Choose a session:`, attendance emojis in upper rows, cancelled reactions in mappings, old Plan legend copy, raw shortcodes in fallback, and missing all-cancelled suppression.

- [ ] **Step 3: Implement same-day labels and natural active mappings**

Add `format_reaction_name_for_fallback` to the imports from `plan_reactions`, then replace `_combined_session_text()` and add the label/mapping helpers:

```python
def _all_sessions_same_date(practices):
    dates = {practice.date.date() for practice in practices}
    return len(dates) == 1


def _combined_session_when(practice, *, same_day):
    if same_day:
        return practice.date.strftime("%-I:%M %p")
    return (
        f"{practice.date.strftime('%A, %B %-d')} · "
        f"{practice.date.strftime('%-I:%M %p')}"
    )


def _combined_owner_label(practice, *, same_day):
    if same_day:
        return practice.date.strftime("%-I:%M %p")
    return practice.date.strftime("%A at %-I:%M %p")


def _join_with_or(items):
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return f"{', '.join(items[:-1])}, or {items[-1]}"


def _combined_mapping(practices, *, plain):
    same_day = _all_sessions_same_date(practices)
    active = [practice for practice in practices if not _is_cancelled(practice)]
    if not active:
        return None
    pairs = []
    for practice in active:
        reaction = (
            format_reaction_name_for_fallback(practice.slack_session_emoji)
            if plain
            else f":{practice.slack_session_emoji}:"
        )
        when = (
            practice.date.strftime("%-I:%M %p")
            if same_day
            else practice.date.strftime("%a at %-I:%M %p")
        )
        pairs.append(f"{reaction} for {when}")
    return _join_with_or(pairs)


def _combined_attendance_sentence(practices, *, plain):
    mapping = _combined_mapping(practices, plain=plain)
    if not mapping:
        return None
    prefix = "RSVP with" if plain else "Bop"
    return f"{prefix} {mapping} so we'll know you'll be there."


def _combined_session_text(practice, *, same_day):
    when = _combined_session_when(practice, same_day=same_day)
    first_line = (
        f"*CANCELLED · {when}*" if _is_cancelled(practice) else f"*{when}*"
    )
    location = practice.location.name if practice.location else "TBD"
    spot = practice.location.spot if practice.location and practice.location.spot else None
    lines = [first_line, location + (f" - {spot}" if spot else "")]
    lead_line = _combined_lead_line(practice)
    if lead_line:
        lines.append(lead_line)
    if _is_cancelled(practice):
        reason_prefix = "Reason: "
        available = max(
            0,
            SECTION_TEXT_MAX - len("\n".join(lines)) - len("\n" + reason_prefix),
        )
        reason_limit = min(_COMBINED_CANCELLATION_REASON_MAX, available)
        if reason_limit > 1:
            reason = truncate_slack_text(
                practice.cancellation_reason or "Cancelled",
                reason_limit,
                field="cancellation_reason",
                surface="combined_practice_announcement",
                practice_id=practice.id,
            )
            lines.append(reason_prefix + reason)
    return "\n".join(lines)
```

- [ ] **Step 4: Rebuild combined Block Kit hierarchy without upper reaction cues**

In `build_combined_lift_blocks()` derive these values immediately after sorting and validation:

```python
same_day = _all_sessions_same_date(ordered)
active = [practice for practice in ordered if not _is_cancelled(practice)]
shared_plan = _shared_plan_reactions(ordered)
```

Replace the `Choose a session:` group with:

```python
session_group = [{
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": _combined_session_text(practice, same_day=same_day),
    },
} for practice in ordered]
```

For divergent Workout and Social rows, replace emoji prefixes with `_combined_owner_label(owner, same_day=same_day)`. Build divergent Notes with an exact heading line:

```python
notes_prefix = "*📝 Notes*\n"
if not same_notes:
    notes_prefix += (
        f"*{_combined_owner_label(owner, same_day=same_day)}*\n"
    )
```

For a shared Notes row, use only `*📝 Notes*\n`. For divergent Workout use:

```python
owner_label = "" if same_workout else (
    f"{_combined_owner_label(owner, same_day=same_day)} · "
)
```

For divergent Social use the same textual owner prefix without bolding or an attendance emoji.

Replace the old ending mapping/Plan legend with:

```python
ending_group = []
attendance = (
    _combined_attendance_sentence(ordered, plain=False) if active else None
)
if attendance:
    ending_group.append(_rsvp_context_block(
        attendance,
        shared_plan,
        surface="combined_practice_announcement",
        practice_id=representative.id,
    ))
```

Keep `active` as the explicit local expression controlling all-cancelled
behavior; do not add a second combined-session state model.

- [ ] **Step 5: Rebuild the combined fallback with a reserved active-only tail**

In the per-session fallback line, remove `session :emoji:` so it ends with the bounded location:

```python
lines.append(
    f"{practice.date.strftime('%A, %B %-d at %-I:%M %p')}; "
    f"{status}; {location}."
)
```

Replace the old mappings/Plan legend/final join with:

```python
attendance = _combined_attendance_sentence(ordered, plain=True)
if not attendance:
    return guard_fallback_text(
        " ".join(lines),
        surface="combined_practice_announcement",
        practice_id=representative.id,
    )

tail_parts = [attendance]
supplemental = format_supplemental_reaction_fallback(
    _shared_plan_reactions(ordered)
)
if supplemental:
    tail_parts.append(supplemental)
tail_parts.append(_FALLBACK_RUNNING_LATE)
return _fallback_with_reserved_tail(
    lines,
    " ".join(tail_parts),
    surface="combined_practice_announcement",
    practice_id=representative.id,
)
```

- [ ] **Step 6: Keep production initial reaction seeds aligned with active mappings**

Import `PracticeStatus` in `app/slack/practices/announcements.py` and change `_seed_combined_reactions()` to:

```python
def _seed_combined_reactions(client, practices):
    active = [
        item for item in practices
        if getattr(item.status, "value", item.status) != PracticeStatus.CANCELLED.value
    ]
    names = [item.slack_session_emoji for item in active]
    if active:
        names.extend(_shared_plan_names(practices))
    for name in dict.fromkeys(names):
        try:
            client.reactions_add(
                channel=practices[0].slack_channel_id,
                timestamp=practices[0].slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not seed :%s: on combined root %s: %s",
                    name,
                    practices[0].slack_message_ts,
                    exc,
                )
```

Add this focused orchestration test to
`tests/slack/test_combined_announcements.py`:

```python
def test_combined_seed_uses_active_attendance_and_full_shared_plan_name(
    app_context,
):
    from app.slack.practices.announcements import _seed_combined_reactions

    plan = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    active = model_practice(1, 14, 18, "six", plan=plan)
    cancelled = model_practice(
        2,
        15,
        19,
        "seven",
        status=PracticeStatus.CANCELLED,
        reason="Facility closed",
        plan=plan,
    )
    for practice in (active, cancelled):
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "123.456"
    client = MagicMock()

    with patch(
        "app.slack.practices.announcements._shared_plan_names",
        return_value=["older_adult::skin-tone-4"],
    ):
        _seed_combined_reactions(client, [active, cancelled])

    assert [
        item.kwargs["name"] for item in client.reactions_add.call_args_list
    ] == ["six", "older_adult::skin-tone-4"]

    client.reset_mock()
    active.status = PracticeStatus.CANCELLED
    with patch(
        "app.slack.practices.announcements._shared_plan_names"
    ) as shared_plan_names:
        _seed_combined_reactions(client, [active, cancelled])
    shared_plan_names.assert_not_called()
    client.reactions_add.assert_not_called()
```

- [ ] **Step 7: Run combined and orchestration tests**

Run:

```bash
env/bin/pytest -q \
  tests/slack/test_combined_announcements.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_reaction_rsvp.py \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/test_scheduler_practice_announcements.py
```

Expected: all selected tests pass. Confirm mixed cancellation removes the cancelled attendance reaction from both visible/fallback mapping and initial seed calls, while the cancelled row and reason remain visible.

- [ ] **Step 8: Commit combined-session polish**

```bash
git add \
  app/slack/blocks/announcements.py \
  app/slack/practices/announcements.py \
  tests/slack/test_combined_announcements.py
git commit -m "feat(slack): simplify combined practice choices"
```

---

### Task 4: Apply the restrained weekly visual language

**Files:**

- Modify: `app/slack/blocks/summary.py`
- Modify: `tests/slack/test_weekly_summary_blocks.py`
- Verify: `tests/agent/test_weekly_summary.py`
- Verify: `tests/slack/test_refresh_delete_exclusion.py`

**Interfaces:**

- Preserves: `build_weekly_summary_blocks(practices, *, week_start, weather_data=None) -> list[dict]`.
- Preserves: `build_weekly_summary_fallback_text(practices, *, week_start, weather_data=None) -> str`.
- No dependency on Tasks 2 or 3.

- [ ] **Step 1: Write exact failing weekly Block Kit tests**

Replace the expectations in
`test_heading_uses_the_explicit_full_calendar_week`,
`test_cancelled_session_stays_visible_without_weather`, and
`test_footer_uses_unique_active_weekdays_and_natural_language` with the exact
tests below. Keep the existing semantic-day grouping and chronological-order
assertions, adding the no-day-calendar assertion shown below.

```python
@pytest.mark.parametrize(
    ("week_start", "expected"),
    [
        (date(2026, 7, 13), "📅 Practices this week · July 13–19"),
        (date(2026, 7, 27), "📅 Practices this week · July 27–August 2"),
        (
            date(2026, 12, 28),
            "📅 Practices this week · December 28, 2026–January 3, 2027",
        ),
    ],
)
def test_heading_uses_one_calendar_emoji_and_explicit_full_week(
    week_start, expected
):
    blocks = build_weekly_summary_blocks(
        [practice(1, datetime.combine(week_start, datetime.min.time()).replace(hour=18))],
        week_start=week_start,
    )
    assert blocks[0]["text"]["text"] == expected
    day_text = "\n".join(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
    )
    assert "📅" not in day_text


def test_cancelled_row_uses_stop_sign_and_suppresses_forecast():
    cancelled = practice(
        2,
        datetime(2026, 8, 2, 9, 0),
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )
    blocks = build_weekly_summary_blocks(
        [cancelled],
        week_start=date(2026, 7, 27),
        weather_data={2: {"temp_f": 92, "conditions": "hot"}},
    )
    text = "\n".join(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
    )
    assert "🚫 CANCELLED · Heat warning" in text
    assert text.count("🚫") == 1
    assert "Forecast:" not in text


def test_active_week_uses_fixed_non_day_specific_footer():
    practices = [
        practice(1, datetime(2026, 7, 27, 6, 0)),
        practice(2, datetime(2026, 7, 27, 18, 0)),
        practice(3, datetime(2026, 7, 30, 18, 0)),
    ]
    contexts = [
        block for block in build_weekly_summary_blocks(
            practices, week_start=date(2026, 7, 27)
        )
        if block.get("type") == "context"
    ]
    assert contexts == [{
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                "📝 Full practice details will be posted before each practice. "
                "· <!channel>"
            ),
        }],
    }]


def test_all_cancelled_week_omits_footer():
    cancelled = practice(
        1,
        datetime(2026, 7, 27, 18, 0),
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )
    blocks = build_weekly_summary_blocks(
        [cancelled], week_start=date(2026, 7, 27)
    )
    assert not any(block.get("type") == "context" for block in blocks)


def test_weekly_fallback_remains_plain_and_has_no_broadcast_token():
    practices = [
        practice(1, datetime(2026, 7, 27, 18, 0)),
        practice(
            2,
            datetime(2026, 8, 2, 9, 0),
            status=PracticeStatus.CANCELLED,
            reason="Heat warning",
        ),
    ]
    fallback = build_weekly_summary_fallback_text(
        practices, week_start=date(2026, 7, 27)
    )
    for forbidden in ("📅", "🚫", "📝", "<!channel>"):
        assert forbidden not in fallback
    assert "Practices this week · July 27–August 2." in fallback
    assert "CANCELLED: Heat warning" in fallback
```

Update existing empty-week and oversized-cancellation expectations so the Block Kit header includes `📅` and the visible cancellation marker includes `🚫`; keep their fallback expectations unchanged.

Use these exact replacements in those existing assertions:

```python
assert header_text(blocks) == "📅 Practices this week · July 13–19"
assert "5:00 PM · 🚫 CANCELLED ·" in day_text
```

- [ ] **Step 2: Run weekly builder tests and verify old heading/footer copy fails**

Run:

```bash
env/bin/pytest -q tests/slack/test_weekly_summary_blocks.py
```

Expected: failures show the missing header/calendar icon, plain cancellation copy, and generated `Daily details posted Mon.` footer.

- [ ] **Step 3: Make the minimal weekly builder changes**

Replace `_weekly_day_text()` with:

```python
def _weekly_day_text(day_practices, weather_data):
    first = day_practices[0]
    if len(day_practices) == 1:
        lines = [
            f"*{first.date.strftime('%A, %B %-d')} · "
            f"{first.date.strftime('%-I:%M %p')}*"
        ]
        if _is_cancelled(first):
            lines.append(
                f"🚫 CANCELLED · {_cancellation_reason(first)}"
            )
            lines.append(
                f"{_practice_kind(first)} · {_location_name(first)}"
            )
        else:
            lines.append(
                f"{_practice_kind(first)} · {_location_name(first)}"
            )
            forecast = _forecast_line(first, weather_data)
            if forecast:
                lines.append(forecast)
        return "\n".join(lines)

    lines = [f"*{first.date.strftime('%A, %B %-d')}*"]
    for practice in day_practices:
        if _is_cancelled(practice):
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · 🚫 CANCELLED · "
                f"{_cancellation_reason(practice)} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
        else:
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
            forecast = _forecast_line(practice, weather_data)
            if forecast:
                lines.append(forecast)
    return "\n".join(lines)
```

Change the header payload to:

```python
"text": f"📅 Practices this week · {_week_range(week_start)}",
```

Remove `_natural_days()` and the `active_days` collection. Append the footer only when at least one ordered practice is active:

```python
if any(not _is_cancelled(practice) for practice in ordered):
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                "📝 Full practice details will be posted before each practice. "
                "· <!channel>"
            ),
        }],
    })
```

Do not change `build_weekly_summary_fallback_text()`.

- [ ] **Step 4: Run weekly builder and scheduling integration tests**

Run:

```bash
env/bin/pytest -q \
  tests/slack/test_weekly_summary_blocks.py \
  tests/agent/test_weekly_summary.py \
  tests/slack/test_refresh_delete_exclusion.py
```

Expected: all selected tests pass; scheduled/refresh callers still use the public builder and no test expects a publication weekday list.

- [ ] **Step 5: Commit weekly polish**

```bash
git add app/slack/blocks/summary.py tests/slack/test_weekly_summary_blocks.py
git commit -m "feat(slack): polish weekly practice summary"
```

---

### Task 5: Update the guarded live matrix and complete verification

**Files:**

- Modify: `scripts/validate_announcement.py`
- Modify: `tests/scripts/test_validate_announcement.py`
- Verify: all files changed by Tasks 1–4
- Runtime state: `validate_posted_ts.json` (ignored; manage only through the harness CLI)

**Interfaces:**

- Preserves: `TEST_CHANNEL = "C07G9RTMRT3"`.
- Preserves: `post()`, `teardown()`, `main(argv=None)`, recursive mention sanitization, immediate state writes, and reply-before-root teardown.
- Adds scenario key: `combined_strength_same_day`.
- Changes scenario data: `multiple_plan_reactions` becomes the approved three-choice Rollerski/Run example.

- [ ] **Step 1: Write failing registry and approved-copy harness tests**

Add `combined_strength_same_day` to `REQUIRED_SCENARIOS` in `tests/scripts/test_validate_announcement.py`, then add:

```python
def test_approved_review_scenarios_render_exact_copy_and_icons():
    standalone = validate.SCENARIOS["multiple_plan_reactions"]
    assert standalone.practices[0].plan_reactions == [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ]
    standalone_blocks, _, _ = validate.build_scenario(
        "multiple_plan_reactions", standalone
    )
    assert (
        "In addition to your attendance emoji, hit a :hatching_chick: for "
        "new rollerskier, a :older_adult::skin-tone-4: for experienced "
        "rollerskier, and a :athletic_shoe: for runner."
    ) in str(standalone_blocks)

    cross_day = validate.SCENARIOS["combined_strength"]
    assert len({item.date.date() for item in cross_day.practices}) == 2
    cross_blocks, _, _ = validate.build_scenario("combined_strength", cross_day)
    assert "Tue at 6:15 PM" in str(cross_blocks)
    assert "Wed at 7:15 PM" in str(cross_blocks)

    same_day = validate.SCENARIOS["combined_strength_same_day"]
    assert len({item.date.date() for item in same_day.practices}) == 1
    same_blocks, _, _ = validate.build_scenario(
        "combined_strength_same_day", same_day
    )
    assert ":six: for 6:05 PM or :seven: for 7:20 PM" in str(same_blocks)

    weekly = validate.SCENARIOS["weekly_cross_month_cancelled"]
    weekly_blocks, weekly_fallback, _ = validate.build_scenario(
        "weekly_cross_month_cancelled", weekly
    )
    assert "📅 Practices this week · July 27–August 2" in str(weekly_blocks)
    assert "🚫 CANCELLED · Heat warning" in str(weekly_blocks)
    assert (
        "📝 Full practice details will be posted before each practice."
        in str(weekly_blocks)
    )
    assert "<!channel>" not in weekly_fallback


def test_harness_passes_full_skin_tone_name_to_reactions_add():
    calls = []
    validate.seed_scenario_reactions(
        _client(reactions_add=lambda **kwargs: calls.append(kwargs)),
        SimpleNamespace(reaction_names=("older_adult::skin-tone-4",)),
        "100.1",
        state=_state(),
    )
    assert [item["name"] for item in calls] == ["older_adult::skin-tone-4"]
```

In the registry loop, calculate expected combined reaction names from active practices only and append shared Plan names only when at least one active session exists. Continue asserting every expected non-checkmark reaction is visibly represented in Block Kit.

- [ ] **Step 2: Run harness tests and verify the missing scenario/old fixtures fail**

Run:

```bash
env/bin/pytest -q tests/scripts/test_validate_announcement.py
```

Expected: failures identify the missing same-day scenario, old two-choice standalone fixture, old weekly copy, and cancelled synthetic reaction seeding.

- [ ] **Step 3: Update synthetic scenarios without weakening harness safety**

Replace `_multiple_plan` with:

```python
_multiple_plan = _practice(
    9,
    datetime(2026, 7, 21, 18, 0),
    activities=[_activity("Rollerski"), _activity("Run")],
    plan_reactions=[
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ],
)
```

Add two same-day Strength fixtures:

```python
_combined_same_day_early = _practice(
    19,
    datetime(2026, 7, 16, 18, 5),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    workout_description="3 x 8 strength circuit",
    logistics_notes="Bring indoor shoes.",
    plan_reactions=_combined_plan,
    slack_session_emoji="six",
)
_combined_same_day_late = _practice(
    20,
    datetime(2026, 7, 16, 19, 20),
    activities=[_activity("Strength")],
    practice_types=[SimpleNamespace(id=2, name="Strength")],
    workout_description="3 x 8 strength circuit",
    logistics_notes="Bring indoor shoes.",
    plan_reactions=_combined_plan,
    slack_session_emoji="seven",
)
```

Register them:

```python
"combined_strength_same_day": _combined(
    _combined_same_day_early,
    _combined_same_day_late,
),
```

Change `_combined()` so synthetic seeds mirror active visible choices:

```python
def _combined(*practices):
    active = tuple(
        practice for practice in practices
        if getattr(practice.status, "value", practice.status)
        != PracticeStatus.CANCELLED.value
    )
    snapshots = [
        tuple((item["emoji"], item["label"]) for item in practice.plan_reactions)
        for practice in practices
    ]
    shared_plan = (
        tuple(item[0] for item in snapshots[0])
        if active
        and snapshots
        and all(snapshot == snapshots[0] for snapshot in snapshots[1:])
        else ()
    )
    return Scenario(
        kind="combined",
        practices=tuple(practices),
        reaction_names=(
            *(practice.slack_session_emoji for practice in active),
            *shared_plan,
        ),
    )
```

Do not change `MENTIONS`, `_sanitize_for_test`, `_assert_test_channel`, `_post_recorded`, `_write_state`, `post`, `teardown`, or the CLI parser.

- [ ] **Step 4: Run the harness and all focused feature tests**

Run:

```bash
env/bin/pytest -q \
  tests/practices/test_plan_reactions.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_announcement_blocks.py \
  tests/slack/test_combined_announcements.py \
  tests/slack/test_weekly_summary_blocks.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_reaction_rsvp.py \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/test_scheduler_practice_announcements.py \
  tests/agent/test_weekly_summary.py \
  tests/scripts/test_validate_announcement.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Run static guards and the full suite**

First run:

```bash
env/bin/python -m py_compile \
  app/practices/plan_reactions.py \
  app/slack/blocks/announcements.py \
  app/slack/practices/announcements.py \
  app/slack/blocks/summary.py \
  scripts/validate_announcement.py
git diff --check
```

Expected: both commands exit 0 with no output.

With the local PostgreSQL test service running, run:

```bash
env/bin/pytest -q tests
```

Expected: the full suite passes with no failures or errors. If PostgreSQL is unavailable, report the connection refusal as an environment blocker and do not describe the suite as passing; the focused pure tests and prior branch baseline do not substitute for a fresh full run.

- [ ] **Step 6: Request independent code and Slack-contract review**

Use `superpowers:requesting-code-review`. Give reviewers the approved addendum and the complete branch diff. Require explicit checks for:

```text
1. Exactly one RSVP context element/newline and one visible <!channel> token.
2. No raw shortcode or broadcast token in top-level fallbacks.
3. Active-only combined mappings/seeds and all-cancelled suppression.
4. Cancelled siblings still influence same-day classification and shared Plan equality.
5. Full older_adult::skin-tone-4 pass-through in storage, rendering, seeding, and events.
6. Complete 2,000/4,000-character required-tail preservation.
7. Exact 📅 / 🚫 / 📝 weekly and Notes payloads.
8. No regression to harness channel/state/teardown guardrails.
```

Resolve review findings with `superpowers:receiving-code-review`, rerun the affected focused command, then rerun Step 5.

- [ ] **Step 7: Commit harness and final automated contracts**

```bash
git add scripts/validate_announcement.py tests/scripts/test_validate_announcement.py
git commit -m "test(slack): refresh announcement review matrix"
```

- [ ] **Step 8: Tear down the current 33-message review run safely**

The current ignored state records 33 messages in `C07G9RTMRT3`. Load the existing workspace environment without printing secrets and invoke the harness API:

```bash
env/bin/python - <<'PY'
from dotenv import load_dotenv

load_dotenv('/Users/rob/env/tcsc-trips/.env', override=False)
from scripts.validate_announcement import main

raise SystemExit(main(['teardown']))
PY
```

Expected: exit 0 and `validate_posted_ts.json` is absent. If teardown exits 1, inspect the retained record/error, rerun teardown, and do not start a new post run until state is empty. Never edit or delete the state file manually.

- [ ] **Step 9: Post the revised synthetic review matrix**

Run:

```bash
env/bin/python - <<'PY'
from dotenv import load_dotenv

load_dotenv('/Users/rob/env/tcsc-trips/.env', override=False)
from scripts.validate_announcement import main

raise SystemExit(main(['post']))
PY
```

Expected: exit 0, one permalink per scenario, a new state file containing only channel `C07G9RTMRT3`, and no recorded reaction errors. If interrupted, teardown the retained state before attempting another post run.

- [ ] **Step 10: Read back every Slack message and verify the approved presentation**

Using the returned permalinks and Slack readback, verify:

```text
- Every root/reply belongs to C07G9RTMRT3 and carries the current harness run marker.
- No test message contains <!channel>, <!here>, or <!everyone>; unit tests own production mention assertions.
- Standalone RSVP is two visual lines in one context block; supplemental text precedes Running late.
- The Rollerski/Run scenario shows chick, modified older-adult, and shoe choices in one natural sentence.
- Cross-day combined shows Tue/Wed only in the bottom mapping and no Choose a session heading.
- Same-day combined shows 6:05 PM / 7:20 PM without repeated day labels.
- Mixed cancellation keeps the cancelled row/reason and excludes its attendance reaction.
- Weekly summary has one calendar icon, no day-row calendars, one stop-sign cancellation, and the memo footer.
- Notes headings use the memo icon and no root shows adjacent dividers or an empty section.
- All Slack header/section/context lengths remain within 150/3,000/2,000 characters.
```

Retain the revised posts and state file for product-owner review. Do not teardown until the user signs off.

- [ ] **Step 11: After sign-off, teardown and prepare branch integration**

Run the Step 8 teardown command again and confirm `validate_posted_ts.json` is absent. Then run:

```bash
git status --short
git log --oneline --decorate -8
```

Expected: only the intentional untracked `env` symlink remains; implementation and test commits are present. Use `superpowers:finishing-a-development-branch` to offer merge, PR, keep, or cleanup options without changing integration state until the user chooses.
